"""JobNimbus API client - read and write."""

import json
import os
import time
from urllib.parse import urlparse

import requests

from cli_anything.jobnimbus.core.query import merge_filters
from cli_anything.jobnimbus.core.resources import (
    CREATE, DELETE, RESOURCES, UPDATE, get_resource,
)


class JobNimbusClientError(Exception):
    """Base exception for API client errors."""

    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class RateLimitError(JobNimbusClientError):
    """Raised when API rate limit is hit."""

    def __init__(self, retry_after=None):
        self.retry_after = retry_after or 5
        super().__init__(f"Rate limited. Retry after {self.retry_after}s", status_code=429)


class AuthenticationError(JobNimbusClientError):
    """Raised on 401/403 responses."""


class ReadOnlyError(JobNimbusClientError):
    """Raised when a write is attempted while the client is locked read-only."""


def _truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


class JobNimbusClient:
    """Client for the JobNimbus public API.

    Writes can be blocked with read_only=True (or JOBNIMBUS_READ_ONLY=1) and
    previewed without sending anything with dry_run=True.
    """

    BASE_URL = "https://app.jobnimbus.com/api1"
    UPLOAD_URL = "https://api.jobnimbus.com/files/v1/uploads"
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 1000
    # The API rejects from >= 10000 with a 400; paginate_all re-anchors past it.
    MAX_WINDOW = 10000
    MAX_RETRIES = 3
    TIMEOUT = 60

    def __init__(self, api_key=None, actor=None, read_only=None, dry_run=False):
        self.api_key = api_key or os.environ.get("JOBNIMBUS_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "No API key provided. Set JOBNIMBUS_API_KEY environment variable "
                "or pass api_key to the client."
            )
        self.actor = actor
        self.read_only = (
            _truthy(os.environ.get("JOBNIMBUS_READ_ONLY")) if read_only is None else read_only
        )
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    # ── HTTP ────────────────────────────────────────────────────────────────

    def _url(self, endpoint):
        """Resolve an endpoint. Full URLs are only allowed on jobnimbus.com hosts
        so the bearer token can never be sent anywhere else."""
        if not endpoint.startswith(("http://", "https://")):
            return f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        parsed = urlparse(endpoint)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or not (host == "jobnimbus.com" or host.endswith(".jobnimbus.com")):
            raise JobNimbusClientError(f"Refusing to send the API key to '{endpoint}'.")
        return endpoint

    def _request(self, method, endpoint, params=None, body=None, stream=False):
        """Execute a request. Retries only on 429 (the request was not processed)."""
        method = method.upper()
        url = self._url(endpoint)
        params = dict(params or {})
        if self.actor:
            params["actor"] = self.actor

        if method != "GET":
            if self.read_only:
                raise ReadOnlyError(
                    f"Blocked {method} {url}: client is read-only "
                    "(JOBNIMBUS_READ_ONLY / --read-only is set)."
                )
            if self.dry_run:
                return {"dry_run": True, "method": method, "url": url,
                        "params": params, "body": body}

        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self.session.request(
                    method, url, params=params, json=body, timeout=self.TIMEOUT, stream=stream,
                )
            except requests.Timeout:
                raise JobNimbusClientError(f"Request timed out after {self.TIMEOUT}s: {method} {url}")
            except requests.RequestException as e:
                raise JobNimbusClientError(f"Connection failed: {e}")

            if resp.status_code == 429:
                retry_after = self._retry_after(resp, attempt)
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(retry_after)
                    continue
                raise RateLimitError(retry_after=retry_after)

            if resp.status_code in (401, 403):
                raise AuthenticationError(
                    f"Authentication failed ({resp.status_code}): {resp.text}",
                    status_code=resp.status_code, response_body=resp.text,
                )
            if not resp.ok:
                raise JobNimbusClientError(
                    f"API error {resp.status_code}: {resp.text}",
                    status_code=resp.status_code, response_body=resp.text,
                )
            if stream:
                return resp
            try:
                return resp.json()
            except ValueError:
                return resp.text

        raise JobNimbusClientError("Max retries exceeded")

    @staticmethod
    def _retry_after(resp, attempt):
        try:
            return max(0, int(resp.headers.get("Retry-After", "")))
        except ValueError:
            return 2 ** attempt

    # ── Read ────────────────────────────────────────────────────────────────

    def list_records(self, resource, size=None, offset=None, sort_field=None,
                     sort_direction=None, filter=None, fields=None):
        """List records. Always returns {"results": [...], "count": N}.

        Args:
            filter: JobNimbus filter dict, e.g. {"must": [{"term": {"city": "Orlando"}}]}
            fields: Comma-separated field names to return
        """
        res = get_resource(resource)
        params = {}
        if size is not None:
            params["size"] = max(1, min(int(size), self.MAX_PAGE_SIZE))
        if offset:
            if int(offset) >= self.MAX_WINDOW:
                raise JobNimbusClientError(
                    f"The API cannot page past offset {self.MAX_WINDOW}. "
                    "Use `export`, or narrow with a query (e.g. a date_created range)."
                )
            params["from"] = int(offset)
        if sort_field:
            params["sort_field"] = sort_field
        if sort_direction:
            params["sort_direction"] = sort_direction.lower()
        if fields:
            params["fields"] = fields
        if filter:
            params["filter"] = json.dumps(filter)

        response = self._request("GET", res.path, params=params)
        if not isinstance(response, dict):
            raise JobNimbusClientError(f"Unexpected list response for {resource}: {str(response)[:200]}")
        rows = response.get(res.list_key) or []
        rest = {k: v for k, v in response.items() if k != res.list_key}
        return {**rest, "results": rows, "count": response.get("count", len(rows))}

    def get_record(self, resource, record_id, fields=None):
        """Get a single record by JNID."""
        res = get_resource(resource)
        if res.single_get:
            params = {"fields": fields} if fields else None
            return self._request("GET", f"{res.path}/{record_id}", params=params)
        # No JSON single-record endpoint for this type: look it up through the list.
        found = self.list_records(
            resource, size=1, fields=fields,
            filter={"must": [{"term": {"jnid": record_id}}]},
        )["results"]
        if not found:
            raise JobNimbusClientError(
                f"API error 404: {resource} record '{record_id}' not found", status_code=404,
            )
        return found[0]

    def count_records(self, resource, filter=None):
        """Count records matching an optional filter (fetches a single jnid, not a page)."""
        return self.list_records(resource, size=1, fields="jnid", filter=filter)["count"]

    def paginate_all(self, resource, page_size=None, sort_field="date_created",
                     sort_direction="asc", filter=None, fields=None, max_records=None):
        """Yield every matching record, re-anchoring on sort_field to get past
        the API's 10,000-record offset window."""
        page_size = min(page_size or self.DEFAULT_PAGE_SIZE, self.MAX_PAGE_SIZE)
        if fields:
            fields = ",".join(dict.fromkeys(fields.split(",") + ["jnid", sort_field]))
        bound = "gte" if (sort_direction or "asc").lower() == "asc" else "lte"
        offset, yielded, anchor = 0, 0, None
        previous_ids, window_ids = set(), set()

        while True:
            page_filter = filter
            if anchor is not None:
                page_filter = merge_filters(
                    filter, {"must": [{"range": {sort_field: {bound: anchor}}}]}
                )
            result = self.list_records(
                resource, size=page_size, offset=offset, sort_field=sort_field,
                sort_direction=sort_direction, filter=page_filter, fields=fields,
            )
            records = result["results"]
            if not records:
                return

            for record in records:
                jnid = record.get("jnid")
                if jnid in previous_ids or jnid in window_ids:
                    continue  # already yielded on the other side of an anchor
                window_ids.add(jnid)
                yield record
                yielded += 1
                if max_records and yielded >= max_records:
                    return

            offset += len(records)
            if offset >= result["count"]:
                return
            if offset + page_size > self.MAX_WINDOW:
                # ponytail: re-anchor on the sort value; breaks only if >10k records
                # share one value of sort_field — sort on a finer field if that happens.
                new_anchor = records[-1].get(sort_field)
                if new_anchor is None or new_anchor == anchor:
                    raise JobNimbusClientError(
                        f"Cannot page past {self.MAX_WINDOW} records sorted by "
                        f"'{sort_field}'. Sort by date_created or narrow the query."
                    )
                anchor, offset = new_anchor, 0
                previous_ids, window_ids = window_ids, set()

    def get_account_settings(self):
        """Get account settings including all workflow definitions and statuses."""
        return self._request("GET", "account/settings")

    def find_record(self, record_id):
        """Find a record by JNID, auto-detecting its type. Returns (resource, record)."""
        for name, res in RESOURCES.items():
            if not res.single_get:
                continue
            try:
                result = self.get_record(name, record_id)
            except AuthenticationError:
                raise
            except JobNimbusClientError as e:
                # v2 endpoints answer 500 instead of 404 for unknown ids.
                if e.status_code == 404 or (e.status_code == 500 and res.path.startswith("v2/")):
                    continue
                raise
            if result:
                return (name, result)
        return (None, None)

    RELATED_RESOURCES = ("jobs", "tasks", "activities", "invoices", "estimates", "files")

    def get_related(self, record_id, resource_type=None, size=100):
        """Get the records linked to a contact or job, keyed by resource type."""
        names = [n for n in self.RELATED_RESOURCES if not (n == "jobs" and resource_type == "job")]
        related_filter = {"must": [{"term": {"related.id": record_id}}]}
        return {
            name: self.list_records(
                name, size=size, sort_field="date_created", sort_direction="desc",
                filter=related_filter,
            )
            for name in names
        }

    # ── Write ───────────────────────────────────────────────────────────────

    def _require_write(self, resource, operation):
        res = get_resource(resource)
        if operation not in res.writes:
            supported = ", ".join(res.writes) or "read-only"
            raise JobNimbusClientError(
                f"The JobNimbus API does not support '{operation}' on {resource} ({supported})."
            )
        return res

    def create_record(self, resource, data):
        """Create a record (POST)."""
        res = self._require_write(resource, CREATE)
        return self._request("POST", res.path, body=data)

    def update_record(self, resource, record_id, data):
        """Update fields on a record (PUT). Only the fields given are changed."""
        res = self._require_write(resource, UPDATE)
        return self._request("PUT", f"{res.path}/{record_id}", body=data)

    def delete_record(self, resource, record_id):
        """Soft-delete a record: the API's delete is PUT {"is_active": false}."""
        res = self._require_write(resource, DELETE)
        return self._request("PUT", f"{res.path}/{record_id}", body={"is_active": False})

    # ── Files ───────────────────────────────────────────────────────────────

    def download_file(self, file_id, dest_path):
        """Download a file attachment's content to dest_path. Returns bytes written."""
        resp = self._request("GET", f"files/{file_id}", stream=True)
        written = 0
        with open(dest_path, "wb") as out:
            for chunk in resp.iter_content(chunk_size=65536):
                out.write(chunk)
                written += len(chunk)
        return written

    def upload_file(self, path, related, file_type=1, description=None, filename=None,
                    is_private=False):
        """Upload a local file and attach it to contacts/jobs (single-part, <100MB).

        file_type: 1=Document 2=Photo 3=Email Attachment 5=Invoice, or a custom type id.
        """
        if not os.path.isfile(path):
            raise JobNimbusClientError(f"File not found: {path}")
        body = {
            "related": list(related),
            "type": int(file_type),
            "filename": filename or os.path.basename(path),
            "isPrivate": bool(is_private),
        }
        if description:
            body["description"] = description
        ticket = self._request("POST", f"{self.UPLOAD_URL}/url", body=body)
        if isinstance(ticket, dict) and ticket.get("dry_run"):
            return ticket
        data = (ticket.get("data") if isinstance(ticket, dict) else None) or {}
        if not data.get("url") or not data.get("jnid"):
            raise JobNimbusClientError(f"Unexpected upload response: {str(ticket)[:300]}")

        # The presigned URL carries its own auth: never send the API key to storage.
        with open(path, "rb") as fh:
            put = requests.put(
                data["url"], data=fh, timeout=self.TIMEOUT * 5,
                headers={"Content-Type": "application/octet-stream"},
            )
        if not put.ok:
            raise JobNimbusClientError(
                f"File upload failed ({put.status_code}): {put.text[:300]}",
                status_code=put.status_code, response_body=put.text,
            )
        done = self._request(
            "POST", f"{self.UPLOAD_URL}/{data['jnid']}/complete",
            params={"generateThumbnail": "true"},
        )
        return {"jnid": data["jnid"], "filename": body["filename"], "complete": done}
