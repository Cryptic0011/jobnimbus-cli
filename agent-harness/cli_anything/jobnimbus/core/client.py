"""JobNimbus API client - READ-ONLY operations only."""

import os
import time
import json
from urllib.parse import urlencode

import requests


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
    pass


class JobNimbusClient:
    """Read-only client for the JobNimbus API.

    This client intentionally only implements GET methods to ensure
    zero data modification during audit tasks.
    """

    BASE_URL = "https://app.jobnimbus.com/api1"
    VALID_RESOURCES = (
        "contacts", "jobs", "tasks", "activities",
        "invoices", "estimates", "files",
    )
    # Products use a v2 endpoint with a different path
    PRODUCTS_ENDPOINT = "v2/products"
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 1000
    MAX_RETRIES = 3
    TIMEOUT = 30

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("JOBNIMBUS_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "No API key provided. Set JOBNIMBUS_API_KEY environment variable "
                "or pass api_key to the client."
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def _request(self, endpoint, params=None):
        """Execute a GET request with retry logic for rate limiting.

        This is the ONLY HTTP method exposed. No POST, PUT, or DELETE.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self.session.get(url, params=params, timeout=self.TIMEOUT)
            except requests.ConnectionError as e:
                raise JobNimbusClientError(f"Connection failed: {e}")
            except requests.Timeout:
                raise JobNimbusClientError(f"Request timed out after {self.TIMEOUT}s")

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(retry_after)
                    continue
                raise RateLimitError(retry_after=retry_after)

            if resp.status_code in (401, 403):
                raise AuthenticationError(
                    f"Authentication failed ({resp.status_code}): {resp.text}",
                    status_code=resp.status_code,
                    response_body=resp.text,
                )

            raise JobNimbusClientError(
                f"API error {resp.status_code}: {resp.text}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        raise JobNimbusClientError("Max retries exceeded")

    def list_records(self, resource, size=None, offset=None, sort_field=None,
                     sort_direction=None, query=None, fields=None, filters=None):
        """List records for a given resource type.

        Args:
            resource: One of VALID_RESOURCES or 'products'
            size: Number of records to return (default 50, max 1000)
            offset: Starting index for pagination (0-based)
            sort_field: Field to sort by (e.g. 'date_updated', 'date_created')
            sort_direction: 'asc' or 'desc'
            query: ElasticSearch query string for filtering
            fields: Comma-separated field names to return
            filters: Dict of additional filter parameters
        """
        if resource == "products":
            endpoint = self.PRODUCTS_ENDPOINT
        elif resource not in self.VALID_RESOURCES:
            raise ValueError(
                f"Invalid resource '{resource}'. Must be one of: "
                f"{self.VALID_RESOURCES + ('products',)}"
            )
        else:
            endpoint = resource

        params = {}

        if size is not None:
            params["size"] = min(int(size), self.MAX_PAGE_SIZE)
        if offset is not None:
            params["from"] = int(offset)
        if sort_field:
            params["sort_field"] = sort_field
        if sort_direction:
            params["sort_direction"] = sort_direction.lower()
        if query:
            params[""] = query  # ES query syntax uses bare ? parameter
        if fields:
            params["fields"] = fields
        if filters:
            for k, v in filters.items():
                params[k] = v

        return self._request(endpoint, params=params)

    def get_record(self, resource, record_id, fields=None):
        """Get a single record by ID.

        Args:
            resource: One of VALID_RESOURCES or 'products'
            record_id: The JNID of the record
            fields: Comma-separated field names to return
        """
        if resource == "products":
            endpoint = f"{self.PRODUCTS_ENDPOINT}/{record_id}"
        elif resource not in self.VALID_RESOURCES:
            raise ValueError(
                f"Invalid resource '{resource}'. Must be one of: "
                f"{self.VALID_RESOURCES + ('products',)}"
            )
        else:
            endpoint = f"{resource}/{record_id}"

        params = {}
        if fields:
            params["fields"] = fields

        return self._request(endpoint, params=params)

    def count_records(self, resource, query=None):
        """Get count of records matching optional query.

        Uses size=0 to avoid transferring record data.
        """
        result = self.list_records(resource, size=0, query=query)
        return result.get("count", 0)

    def paginate_all(self, resource, page_size=None, sort_field=None,
                     sort_direction=None, query=None, fields=None, filters=None,
                     max_records=None):
        """Generator that yields all records across pages.

        Args:
            max_records: Stop after this many records (None = all)
        """
        page_size = min(page_size or self.DEFAULT_PAGE_SIZE, self.MAX_PAGE_SIZE)
        offset = 0
        yielded = 0

        while True:
            result = self.list_records(
                resource,
                size=page_size,
                offset=offset,
                sort_field=sort_field,
                sort_direction=sort_direction,
                query=query,
                fields=fields,
                filters=filters,
            )

            records = result.get("results", [])
            if not records:
                break

            for record in records:
                yield record
                yielded += 1
                if max_records and yielded >= max_records:
                    return

            total = result.get("count", 0)
            offset += len(records)
            if offset >= total:
                break

    def get_account_settings(self):
        """Get account settings including all workflow definitions and statuses."""
        return self._request("account/settings")

    def find_record(self, record_id):
        """Find a record by JNID, auto-detecting its resource type.

        Tries each resource type until found. Returns (resource_type, record) tuple.
        """
        for resource in self.VALID_RESOURCES + ("products",):
            try:
                result = self.get_record(resource, record_id)
                if result:
                    return (resource, result)
            except JobNimbusClientError as e:
                if e.status_code == 404 or (e.status_code and e.status_code >= 400):
                    continue
                raise
        return (None, None)

    def get_related(self, record_id, resource_type=None):
        """Get all records related to a contact or job.

        Args:
            record_id: JNID of the contact or job
            resource_type: 'contact' or 'job' (auto-detected if None)

        Returns dict with keys for each related resource type.
        """
        related = {}

        if resource_type is None:
            # Try to detect: fetch the record first
            rtype, record = self.find_record(record_id)
            if rtype == "contacts":
                resource_type = "contact"
            elif rtype == "jobs":
                resource_type = "job"
            else:
                resource_type = "contact"  # default guess

        if resource_type == "contact":
            # Jobs for this contact
            try:
                related["jobs"] = self.list_records(
                    "jobs", size=100, filters={"primary_id": record_id}
                )
            except JobNimbusClientError:
                related["jobs"] = {"results": [], "count": 0}

            # Tasks for this contact
            try:
                related["tasks"] = self.list_records(
                    "tasks", size=100, filters={"related_contact": record_id}
                )
            except JobNimbusClientError:
                related["tasks"] = {"results": [], "count": 0}

            # Activities for this contact
            try:
                related["activities"] = self.list_records(
                    "activities", size=100, filters={"primary_id": record_id}
                )
            except JobNimbusClientError:
                related["activities"] = {"results": [], "count": 0}

            # Invoices for this contact
            try:
                related["invoices"] = self.list_records(
                    "invoices", size=100, filters={"primary_id": record_id}
                )
            except JobNimbusClientError:
                related["invoices"] = {"results": [], "count": 0}

            # Estimates for this contact
            try:
                related["estimates"] = self.list_records(
                    "estimates", size=100, filters={"primary_id": record_id}
                )
            except JobNimbusClientError:
                related["estimates"] = {"results": [], "count": 0}

        elif resource_type == "job":
            # Tasks for this job
            try:
                related["tasks"] = self.list_records(
                    "tasks", size=100, filters={"related_job": record_id}
                )
            except JobNimbusClientError:
                related["tasks"] = {"results": [], "count": 0}

            # Activities for this job
            try:
                related["activities"] = self.list_records(
                    "activities", size=100, filters={"job_id": record_id}
                )
            except JobNimbusClientError:
                related["activities"] = {"results": [], "count": 0}

            # Invoices for this job
            try:
                related["invoices"] = self.list_records(
                    "invoices", size=100, filters={"job_id": record_id}
                )
            except JobNimbusClientError:
                related["invoices"] = {"results": [], "count": 0}

            # Estimates for this job
            try:
                related["estimates"] = self.list_records(
                    "estimates", size=100, filters={"job_id": record_id}
                )
            except JobNimbusClientError:
                related["estimates"] = {"results": [], "count": 0}

        return related
