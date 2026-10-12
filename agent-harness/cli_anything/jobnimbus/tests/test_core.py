"""Unit tests for the JobNimbus client and formatting — synthetic data, no network."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from cli_anything.jobnimbus.core.client import (
    AuthenticationError,
    JobNimbusClient,
    JobNimbusClientError,
    RateLimitError,
    ReadOnlyError,
)
from cli_anything.jobnimbus.utils.formatting import (
    format_json,
    format_record_summary,
    format_table,
    output_results,
    unix_to_iso,
)


def make_response(status=200, body=None, headers=None, text=None):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.headers = headers or {}
    resp.text = text if text is not None else json.dumps(body)
    if body is None and text is not None:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = body
    return resp


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("JOBNIMBUS_READ_ONLY", raising=False)
    c = JobNimbusClient(api_key="test-key")
    c.session.request = MagicMock(return_value=make_response(body={"results": [], "count": 0}))
    return c


def sent(client, index=-1):
    """(method, url, kwargs) of a request the client sent."""
    args, kwargs = client.session.request.call_args_list[index]
    return args[0], args[1], kwargs


# ── Client Tests ────────────────────────────────────────────────────────────

class TestClientInit:
    def test_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AuthenticationError, match="No API key"):
                JobNimbusClient()

    def test_explicit_key_overrides_env(self):
        with patch.dict(os.environ, {"JOBNIMBUS_API_KEY": "env-key"}):
            assert JobNimbusClient().api_key == "env-key"
            c = JobNimbusClient(api_key="explicit-key")
            assert c.session.headers["Authorization"] == "Bearer explicit-key"

    def test_read_only_from_env(self):
        with patch.dict(os.environ, {"JOBNIMBUS_READ_ONLY": "1"}):
            assert JobNimbusClient(api_key="k").read_only is True
            assert JobNimbusClient(api_key="k", read_only=False).read_only is False
        with patch.dict(os.environ, {"JOBNIMBUS_READ_ONLY": "0"}):
            assert JobNimbusClient(api_key="k").read_only is False


class TestRequests:
    def test_auth_errors(self, client):
        for status in (401, 403):
            client.session.request.return_value = make_response(status, text="nope")
            with pytest.raises(AuthenticationError):
                client._request("GET", "contacts")

    def test_rate_limit_retries_then_succeeds(self, client):
        client.session.request.side_effect = [
            make_response(429, headers={"Retry-After": "0"}),
            make_response(body={"count": 0}),
        ]
        assert client._request("GET", "contacts") == {"count": 0}

    def test_rate_limit_exhausted(self, client):
        client.session.request.return_value = make_response(429, headers={"Retry-After": "0"})
        with pytest.raises(RateLimitError):
            client._request("GET", "contacts")

    def test_retry_after_http_date_does_not_crash(self, client):
        resp = make_response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
        assert client._retry_after(resp, 0) == 1

    def test_server_error(self, client):
        client.session.request.return_value = make_response(500, text="Internal Server Error")
        with pytest.raises(JobNimbusClientError, match="500") as exc:
            client._request("GET", "contacts")
        assert exc.value.status_code == 500

    def test_non_json_success_returns_text(self, client):
        client.session.request.return_value = make_response(200, text="OK")
        assert client._request("GET", "whatever") == "OK"

    def test_2xx_is_success(self, client):
        client.session.request.return_value = make_response(201, body={"jnid": "new"})
        assert client._request("POST", "contacts", body={})["jnid"] == "new"

    def test_actor_added_to_every_request(self, client):
        client.actor = "sam@company.com"
        client.list_records("contacts")
        assert sent(client)[2]["params"]["actor"] == "sam@company.com"

    def test_refuses_to_send_key_to_other_hosts(self, client):
        for url in ("https://example.com/x", "http://app.jobnimbus.com/api1/contacts",
                    "https://jobnimbus.com.evil.io/x"):
            with pytest.raises(JobNimbusClientError, match="Refusing"):
                client._request("GET", url)
        client.session.request.assert_not_called()

    def test_allows_jobnimbus_hosts(self, client):
        client._request("GET", "https://api.jobnimbus.com/files/v1/x")
        assert sent(client)[1] == "https://api.jobnimbus.com/files/v1/x"


class TestListRecords:
    def test_rejects_invalid_resource(self, client):
        with pytest.raises(ValueError, match="Invalid resource"):
            client.list_records("widgets")

    def test_v2_endpoints(self, client):
        for resource, path in (("invoices", "v2/invoices"), ("estimates", "v2/estimates"),
                               ("products", "v2/products"), ("contacts", "contacts")):
            client.list_records(resource)
            assert sent(client)[1] == f"{client.BASE_URL}/{path}"

    def test_filter_sent_as_json_param(self, client):
        flt = {"must": [{"term": {"status_name": "Lead"}}]}
        client.list_records("contacts", filter=flt, sort_field="date_created",
                            sort_direction="ASC", fields="jnid", size=5000, offset=20)
        params = sent(client)[2]["params"]
        assert json.loads(params["filter"]) == flt
        assert params["sort_direction"] == "asc"
        assert params["size"] == 1000
        assert params["from"] == 20
        assert "" not in params  # the old bare ?=query parameter the API ignored

    def test_normalizes_activity_and_files_keys(self, client):
        for resource, key in (("activities", "activity"), ("files", "files")):
            client.session.request.return_value = make_response(body={key: [{"jnid": "a"}], "count": 9})
            assert client.list_records(resource) == {"results": [{"jnid": "a"}], "count": 9}

    def test_offset_past_window_rejected(self, client):
        with pytest.raises(JobNimbusClientError, match="10000"):
            client.list_records("contacts", offset=10000)

    def test_count_fetches_one_jnid_not_a_page(self, client):
        client.session.request.return_value = make_response(body={"results": [{"jnid": "a"}], "count": 28152})
        assert client.count_records("contacts") == 28152
        params = sent(client)[2]["params"]
        assert params["size"] == 1 and params["fields"] == "jnid"


class TestGetRecord:
    def test_single_get(self, client):
        client.session.request.return_value = make_response(body={"jnid": "inv1"})
        assert client.get_record("invoices", "inv1")["jnid"] == "inv1"
        assert sent(client)[1].endswith("/v2/invoices/inv1")

    def test_files_get_uses_list_lookup(self, client):
        """GET files/<id> returns the file's bytes, so metadata comes from the list."""
        client.session.request.return_value = make_response(body={"files": [{"jnid": "f1"}], "count": 1})
        assert client.get_record("files", "f1") == {"jnid": "f1"}
        _, url, kwargs = sent(client)
        assert url.endswith("/files")
        assert json.loads(kwargs["params"]["filter"]) == {"must": [{"term": {"jnid": "f1"}}]}

    def test_list_lookup_not_found(self, client):
        with pytest.raises(JobNimbusClientError) as exc:
            client.get_record("payments", "nope")
        assert exc.value.status_code == 404


class TestPagination:
    def pages(self, client, *pages):
        client.list_records = MagicMock(side_effect=[
            {"results": rows, "count": count} for rows, count in pages
        ])

    def test_multi_page(self, client):
        self.pages(client, ([{"jnid": "a"}, {"jnid": "b"}], 3), ([{"jnid": "c"}], 3))
        assert [r["jnid"] for r in client.paginate_all("contacts", page_size=2)] == ["a", "b", "c"]

    def test_max_records(self, client):
        self.pages(client, ([{"jnid": f"r{i}"} for i in range(10)], 100))
        assert len(list(client.paginate_all("contacts", page_size=10, max_records=5))) == 5

    def test_empty(self, client):
        self.pages(client, ([], 0))
        assert list(client.paginate_all("contacts")) == []

    def test_reanchors_past_the_offset_window(self, client):
        client.MAX_WINDOW = 4
        rows = [{"jnid": f"r{i}", "date_created": 100 + i} for i in range(6)]
        self.pages(client, (rows[0:2], 6), (rows[2:4], 6), (rows[3:5], 3), (rows[5:6], 3))
        user_filter = {"must": [{"term": {"city": "Orlando"}}]}
        got = list(client.paginate_all("contacts", page_size=2, filter=user_filter))
        assert [r["jnid"] for r in got] == [f"r{i}" for i in range(6)]  # r3 not duplicated
        third = client.list_records.call_args_list[2].kwargs
        assert third["offset"] == 0
        assert third["filter"]["must"] == [
            {"term": {"city": "Orlando"}}, {"range": {"date_created": {"gte": 103}}},
        ]
        assert user_filter == {"must": [{"term": {"city": "Orlando"}}]}  # not mutated

    def test_reanchor_stuck_raises(self, client):
        client.MAX_WINDOW = 2
        same = [{"jnid": "a", "date_created": 5}, {"jnid": "b", "date_created": 5}]
        self.pages(client, (same, 9), (same, 9))
        with pytest.raises(JobNimbusClientError, match="Cannot page past"):
            list(client.paginate_all("contacts", page_size=2))


class TestFindAndRelated:
    def test_find_skips_404_until_found(self, client):
        def fake_get(resource, record_id, fields=None):
            if resource == "jobs":
                return {"jnid": "xyz"}
            raise JobNimbusClientError("Not found", status_code=404)
        client.get_record = MagicMock(side_effect=fake_get)
        assert client.find_record("xyz") == ("jobs", {"jnid": "xyz"})

    def test_find_not_found(self, client):
        client.get_record = MagicMock(side_effect=JobNimbusClientError("x", status_code=404))
        assert client.find_record("nope") == (None, None)

    def test_find_does_not_hide_auth_or_server_errors(self, client):
        client.get_record = MagicMock(side_effect=AuthenticationError("bad key", status_code=401))
        with pytest.raises(AuthenticationError):
            client.find_record("x")
        client.get_record = MagicMock(side_effect=JobNimbusClientError("down", status_code=503))
        with pytest.raises(JobNimbusClientError, match="down"):
            client.find_record("x")

    def test_related_filters_on_related_id(self, client):
        client.list_records = MagicMock(return_value={"results": [], "count": 0})
        related = client.get_related("c1")
        assert set(related) == {"jobs", "tasks", "activities", "invoices", "estimates", "files"}
        for call in client.list_records.call_args_list:
            assert call.kwargs["filter"] == {"must": [{"term": {"related.id": "c1"}}]}
        assert "jobs" not in client.get_related("j1", resource_type="job")

    def test_related_does_not_swallow_errors(self, client):
        client.list_records = MagicMock(side_effect=JobNimbusClientError("fail"))
        with pytest.raises(JobNimbusClientError):
            client.get_related("x")


# ── Write Tests ─────────────────────────────────────────────────────────────

class TestWrites:
    def test_create_posts_body(self, client):
        client.create_record("contacts", {"first_name": "A"})
        method, url, kwargs = sent(client)
        assert (method, url) == ("POST", f"{client.BASE_URL}/contacts")
        assert kwargs["json"] == {"first_name": "A"}

    def test_update_puts_to_record(self, client):
        client.update_record("invoices", "inv1", {"internal_note": "x"})
        method, url, kwargs = sent(client)
        assert (method, url) == ("PUT", f"{client.BASE_URL}/v2/invoices/inv1")
        assert kwargs["json"] == {"internal_note": "x"}

    def test_delete_is_soft(self, client):
        client.delete_record("jobs", "j1")
        method, url, kwargs = sent(client)
        assert (method, url) == ("PUT", f"{client.BASE_URL}/jobs/j1")
        assert kwargs["json"] == {"is_active": False}

    def test_unsupported_writes_rejected_before_any_request(self, client):
        for call in (lambda: client.delete_record("activities", "a1"),
                     lambda: client.delete_record("files", "f1"),
                     lambda: client.create_record("files", {}),
                     lambda: client.update_record("payments", "p1", {"a": 1}),
                     lambda: client.create_record("payments", {})):
            with pytest.raises(JobNimbusClientError, match="does not support"):
                call()
        client.session.request.assert_not_called()

    def test_read_only_blocks_every_write(self, client):
        client.read_only = True
        for call in (lambda: client.create_record("contacts", {"a": 1}),
                     lambda: client.update_record("contacts", "c1", {"a": 1}),
                     lambda: client.delete_record("contacts", "c1"),
                     lambda: client._request("POST", "account/leadsource", body={}),
                     lambda: client.upload_file(__file__, ["c1"])):
            with pytest.raises(ReadOnlyError):
                call()
        client.session.request.assert_not_called()
        client.list_records("contacts")  # reads still work
        assert sent(client)[0] == "GET"

    def test_dry_run_sends_nothing(self, client):
        client.dry_run = True
        result = client.update_record("contacts", "c1", {"zip": "32806"})
        assert result == {
            "dry_run": True, "method": "PUT", "url": f"{client.BASE_URL}/contacts/c1",
            "params": {}, "body": {"zip": "32806"},
        }
        assert client.upload_file(__file__, ["c1"])["dry_run"] is True
        client.session.request.assert_not_called()

    def test_writes_are_not_retried_on_timeout(self, client):
        import requests
        client.session.request.side_effect = requests.Timeout()
        with pytest.raises(JobNimbusClientError, match="timed out"):
            client.create_record("contacts", {"a": 1})
        assert client.session.request.call_count == 1


class TestFiles:
    def test_upload_flow(self, client, tmp_path):
        local = tmp_path / "roof.jpg"
        local.write_bytes(b"jpegbytes")
        client.session.request.side_effect = [
            make_response(body={"data": {"url": "https://s3.example/presigned", "jnid": "f9"}}),
            make_response(body={"data": {"jnid": "f9"}}),
        ]
        with patch("cli_anything.jobnimbus.core.client.requests.put",
                   return_value=make_response(200, text="")) as put:
            result = client.upload_file(str(local), ["job1"], file_type=2, description="front")

        assert result["jnid"] == "f9"
        method, url, kwargs = sent(client, 0)
        assert (method, url) == ("POST", "https://api.jobnimbus.com/files/v1/uploads/url")
        assert kwargs["json"] == {"related": ["job1"], "type": 2, "filename": "roof.jpg",
                                  "isPrivate": False, "description": "front"}
        assert put.call_args.args[0] == "https://s3.example/presigned"
        assert "Authorization" not in put.call_args.kwargs["headers"]  # key never goes to storage
        assert sent(client, 1)[1].endswith("/uploads/f9/complete")

    def test_upload_missing_file_fails_before_any_request(self, client):
        with pytest.raises(JobNimbusClientError, match="File not found"):
            client.upload_file("/no/such/file.pdf", ["c1"])
        client.session.request.assert_not_called()

    def test_download_writes_bytes(self, client, tmp_path):
        resp = make_response(200, text="")
        resp.iter_content.return_value = [b"abc", b"de"]
        client.session.request.return_value = resp
        dest = tmp_path / "out.pdf"
        assert client.download_file("f1", str(dest)) == 5
        assert dest.read_bytes() == b"abcde"


# ── Formatting Tests ────────────────────────────────────────────────────────

class TestUnixToISO:
    def test_valid_timestamp(self):
        result = unix_to_iso(1700000000)
        assert "2023-11-14" in result

    def test_none_returns_none(self):
        assert unix_to_iso(None) is None

    def test_invalid_returns_string(self):
        assert unix_to_iso("not-a-timestamp") == "not-a-timestamp"

    def test_string_timestamp(self):
        result = unix_to_iso("1700000000")
        assert "2023-11-14" in result


class TestFormatTable:
    def test_empty_records(self):
        assert format_table([]) == "(no records)"

    def test_basic_table(self):
        records = [
            {"name": "Alice", "status": "Active"},
            {"name": "Bob", "status": "Inactive"},
        ]
        result = format_table(records)
        assert "Alice" in result
        assert "Bob" in result
        assert "name" in result

    def test_custom_columns(self):
        records = [{"a": 1, "b": 2, "c": 3}]
        result = format_table(records, columns=["a", "c"])
        assert "a" in result
        assert "c" in result
        assert "b" not in result

    def test_max_width_truncation(self):
        records = [{"long_field": "x" * 100}]
        result = format_table(records, max_width=20)
        assert "..." in result

    def test_handles_nested_values(self):
        records = [{"data": {"nested": True}}]
        result = format_table(records)
        assert "nested" in result


class TestFormatRecordSummary:
    def test_contact_summary(self):
        record = {
            "jnid": "abc123",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "status_name": "Lead",
        }
        result = format_record_summary(record, "contacts")
        assert "John Doe" in result
        assert "john@example.com" in result
        assert "Lead" in result

    def test_job_summary(self):
        record = {
            "jnid": "job456",
            "name": "Roof Replacement",
            "status_name": "In Progress",
            "number": "J-001",
        }
        result = format_record_summary(record, "jobs")
        assert "Roof Replacement" in result
        assert "In Progress" in result

    def test_task_summary(self):
        record = {
            "jnid": "task789",
            "title": "Schedule inspection",
            "status": "Open",
            "due_date": 1700000000,
        }
        result = format_record_summary(record, "tasks")
        assert "Schedule inspection" in result
        assert "Open" in result

    def test_activity_summary_truncation(self):
        record = {
            "jnid": "act111",
            "note": "x" * 300,
            "record_type_name": "note",
        }
        result = format_record_summary(record, "activities")
        assert "..." in result
        assert len(result.split("Note: ")[1].split("\n")[0]) <= 200


class TestFormatJSON:
    def test_produces_valid_json(self):
        data = {"key": "value", "nested": {"a": 1}}
        result = format_json(data)
        parsed = json.loads(result)
        assert parsed["key"] == "value"


class TestFormatNewResources:
    def test_invoice_summary(self):
        record = {
            "jnid": "inv1",
            "number": "INV-001",
            "status": "Unpaid",
            "total": 1500.50,
            "subtotal": 1400.00,
        }
        result = format_record_summary(record, "invoices")
        assert "INV-001" in result
        assert "Unpaid" in result
        assert "$1500.50" in result

    def test_estimate_summary(self):
        record = {
            "jnid": "est1",
            "number": "EST-001",
            "status": "Approved",
            "total": 8000.00,
        }
        result = format_record_summary(record, "estimates")
        assert "EST-001" in result
        assert "Approved" in result
        assert "$8000.00" in result

    def test_product_summary(self):
        record = {
            "jnid": "p1",
            "name": "Architectural Shingles",
            "sku": "SHIN-001",
            "item_type": "material",
            "is_active": True,
        }
        result = format_record_summary(record, "products")
        assert "Architectural Shingles" in result
        assert "SHIN-001" in result
        assert "material" in result

    def test_file_summary(self):
        record = {
            "jnid": "f1",
            "filename": "contract.pdf",
            "content_type": "application/pdf",
            "size": 102400,
        }
        result = format_record_summary(record, "files")
        assert "contract.pdf" in result
        assert "application/pdf" in result


class TestOutputResults:
    def test_single_record_is_summarized_not_reported_empty(self, capsys):
        output_results({"jnid": "c1", "first_name": "John", "last_name": "Doe"}, resource_type="contacts")
        out = capsys.readouterr().out
        assert "John Doe" in out and "no records" not in out

    def test_string_totals_do_not_crash(self):
        assert "$12.50" in format_record_summary({"jnid": "i", "total": "12.5"}, "invoices")
        assert "n/a" in format_record_summary({"jnid": "i", "total": "n/a"}, "invoices")

    def test_status_name_preferred_over_numeric_status(self):
        out = format_record_summary({"jnid": "i", "status": 4, "status_name": "Closed"}, "invoices")
        assert "Closed" in out
