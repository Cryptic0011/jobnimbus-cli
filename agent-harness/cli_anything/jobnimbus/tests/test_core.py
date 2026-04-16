"""Unit tests for JobNimbus CLI — uses synthetic data, no external deps."""

import json
import os
import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest

from cli_anything.jobnimbus.core.client import (
    JobNimbusClient,
    JobNimbusClientError,
    AuthenticationError,
    RateLimitError,
)
from cli_anything.jobnimbus.utils.formatting import (
    unix_to_iso,
    format_json,
    format_table,
    format_record_summary,
    output_results,
)


# ── Client Tests ────────────────────────────────────────────────────────────

class TestClientInit:
    def test_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("JOBNIMBUS_API_KEY", None)
            with pytest.raises(AuthenticationError, match="No API key"):
                JobNimbusClient()

    def test_accepts_explicit_key(self):
        client = JobNimbusClient(api_key="test-key-123")
        assert client.api_key == "test-key-123"

    def test_reads_env_var(self):
        with patch.dict(os.environ, {"JOBNIMBUS_API_KEY": "env-key-456"}):
            client = JobNimbusClient()
            assert client.api_key == "env-key-456"

    def test_explicit_key_overrides_env(self):
        with patch.dict(os.environ, {"JOBNIMBUS_API_KEY": "env-key"}):
            client = JobNimbusClient(api_key="explicit-key")
            assert client.api_key == "explicit-key"

    def test_auth_header_set(self):
        client = JobNimbusClient(api_key="test-key")
        assert client.session.headers["Authorization"] == "Bearer test-key"


class TestClientValidation:
    def setup_method(self):
        self.client = JobNimbusClient(api_key="test-key")

    def test_rejects_invalid_resource(self):
        with pytest.raises(ValueError, match="Invalid resource"):
            self.client.list_records("widgets")

    def test_accepts_valid_resources(self):
        for resource in ("contacts", "jobs", "tasks", "activities",
                         "invoices", "estimates", "files"):
            assert resource in JobNimbusClient.VALID_RESOURCES

    def test_accepts_products_resource(self):
        """Products use v2 endpoint but are still valid."""
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [], "count": 0}
            self.client.list_records("products")
            endpoint = mock_req.call_args[0][0]
            assert "v2/products" in endpoint

    def test_size_capped_at_max(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [], "count": 0}
            self.client.list_records("contacts", size=5000)
            call_params = mock_req.call_args[1].get("params") or mock_req.call_args[0][1]
            assert call_params["size"] == 1000


class TestClientRequests:
    def setup_method(self):
        self.client = JobNimbusClient(api_key="test-key")

    @patch("cli_anything.jobnimbus.core.client.requests.Session.get")
    def test_successful_get(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"jnid": "abc"}], "count": 1}
        mock_get.return_value = mock_resp

        result = self.client._request("contacts")
        assert result["count"] == 1

    @patch("cli_anything.jobnimbus.core.client.requests.Session.get")
    def test_auth_error_401(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_get.return_value = mock_resp

        with pytest.raises(AuthenticationError):
            self.client._request("contacts")

    @patch("cli_anything.jobnimbus.core.client.requests.Session.get")
    def test_auth_error_403(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        mock_get.return_value = mock_resp

        with pytest.raises(AuthenticationError):
            self.client._request("contacts")

    @patch("cli_anything.jobnimbus.core.client.requests.Session.get")
    def test_rate_limit_retry(self, mock_get):
        rate_resp = MagicMock()
        rate_resp.status_code = 429
        rate_resp.headers = {"Retry-After": "0"}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"results": [], "count": 0}

        mock_get.side_effect = [rate_resp, ok_resp]
        result = self.client._request("contacts")
        assert result["count"] == 0

    @patch("cli_anything.jobnimbus.core.client.requests.Session.get")
    def test_rate_limit_exhausted(self, mock_get):
        rate_resp = MagicMock()
        rate_resp.status_code = 429
        rate_resp.headers = {"Retry-After": "0"}
        mock_get.return_value = rate_resp

        with pytest.raises(RateLimitError):
            self.client._request("contacts")

    @patch("cli_anything.jobnimbus.core.client.requests.Session.get")
    def test_server_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_get.return_value = mock_resp

        with pytest.raises(JobNimbusClientError, match="500"):
            self.client._request("contacts")


class TestClientPagination:
    def setup_method(self):
        self.client = JobNimbusClient(api_key="test-key")

    def test_paginate_all_single_page(self):
        with patch.object(self.client, "list_records") as mock_list:
            mock_list.return_value = {
                "results": [{"jnid": "a"}, {"jnid": "b"}],
                "count": 2,
            }
            records = list(self.client.paginate_all("contacts", page_size=10))
            assert len(records) == 2

    def test_paginate_all_multi_page(self):
        with patch.object(self.client, "list_records") as mock_list:
            mock_list.side_effect = [
                {"results": [{"jnid": "a"}, {"jnid": "b"}], "count": 3},
                {"results": [{"jnid": "c"}], "count": 3},
            ]
            records = list(self.client.paginate_all("contacts", page_size=2))
            assert len(records) == 3

    def test_paginate_all_max_records(self):
        with patch.object(self.client, "list_records") as mock_list:
            mock_list.return_value = {
                "results": [{"jnid": f"r{i}"} for i in range(10)],
                "count": 100,
            }
            records = list(self.client.paginate_all("contacts", page_size=10, max_records=5))
            assert len(records) == 5

    def test_paginate_all_empty(self):
        with patch.object(self.client, "list_records") as mock_list:
            mock_list.return_value = {"results": [], "count": 0}
            records = list(self.client.paginate_all("contacts"))
            assert len(records) == 0


class TestListRecordParams:
    def setup_method(self):
        self.client = JobNimbusClient(api_key="test-key")

    def test_query_param_mapping(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [], "count": 0}
            self.client.list_records("contacts", query="status_name:Lead")
            params = mock_req.call_args[1].get("params") or mock_req.call_args[0][1]
            assert params[""] == "status_name:Lead"

    def test_sort_params(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [], "count": 0}
            self.client.list_records("contacts", sort_field="date_created", sort_direction="ASC")
            params = mock_req.call_args[1].get("params") or mock_req.call_args[0][1]
            assert params["sort_field"] == "date_created"
            assert params["sort_direction"] == "asc"

    def test_fields_param(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [], "count": 0}
            self.client.list_records("activities", fields="note,date_created")
            params = mock_req.call_args[1].get("params") or mock_req.call_args[0][1]
            assert params["fields"] == "note,date_created"

    def test_filters_passed(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [], "count": 0}
            self.client.list_records("contacts", filters={"status": "Lead"})
            params = mock_req.call_args[1].get("params") or mock_req.call_args[0][1]
            assert params["status"] == "Lead"

    def test_activities_response_normalized_from_activity_key(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {
                "activity": [{"jnid": "act1", "record_type_name": "Note"}],
                "count": 1,
            }
            result = self.client.list_records("activities", size=10)
            assert result["count"] == 1
            assert result["results"] == [{"jnid": "act1", "record_type_name": "Note"}]
            assert result["activity"] == [{"jnid": "act1", "record_type_name": "Note"}]

    def test_non_activity_response_not_rewritten(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"contacts": [{"jnid": "c1"}], "count": 1}
            result = self.client.list_records("contacts", size=10)
            assert "results" not in result
            assert result["contacts"] == [{"jnid": "c1"}]


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


# ── Read-Only Guarantee Tests ───────────────────────────────────────────────

class TestReadOnlyGuarantee:
    """Verify the client has NO write methods."""

    def test_no_post_method(self):
        client = JobNimbusClient(api_key="test")
        assert not hasattr(client, "create_record")
        assert not hasattr(client, "post")

    def test_no_put_method(self):
        client = JobNimbusClient(api_key="test")
        assert not hasattr(client, "update_record")
        assert not hasattr(client, "put")

    def test_no_delete_method(self):
        client = JobNimbusClient(api_key="test")
        assert not hasattr(client, "delete_record")
        assert not hasattr(client, "delete")

    def test_only_get_in_request(self):
        """The _request method only uses session.get, never post/put/delete."""
        import inspect
        source = inspect.getsource(JobNimbusClient._request)
        assert "session.get" in source or "self.session.get" in source
        assert "session.post" not in source
        assert "session.put" not in source
        assert "session.delete" not in source


# ── New Resource Tests ──────────────────────────────────────────────────────

class TestNewResources:
    def setup_method(self):
        self.client = JobNimbusClient(api_key="test-key")

    def test_list_invoices(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [{"jnid": "inv1", "total": 500.0}], "count": 1}
            result = self.client.list_records("invoices", size=10)
            assert result["count"] == 1
            mock_req.assert_called_once()

    def test_list_estimates(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [{"jnid": "est1"}], "count": 1}
            result = self.client.list_records("estimates", size=10)
            assert result["count"] == 1

    def test_list_files(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [{"jnid": "f1", "filename": "doc.pdf"}], "count": 1}
            result = self.client.list_records("files", size=10)
            assert result["count"] == 1

    def test_products_uses_v2_endpoint(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"results": [], "count": 0}
            self.client.list_records("products")
            endpoint = mock_req.call_args[0][0]
            assert endpoint == "v2/products"

    def test_get_product_uses_v2_endpoint(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"jnid": "prod1", "name": "Shingle"}
            self.client.get_record("products", "prod1")
            endpoint = mock_req.call_args[0][0]
            assert endpoint == "v2/products/prod1"

    def test_get_account_settings(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"workflows": [{"name": "Sales"}]}
            result = self.client.get_account_settings()
            mock_req.assert_called_with("account/settings")
            assert "workflows" in result

    def test_paginate_all_uses_normalized_activity_results(self):
        with patch.object(self.client, "_request") as mock_req:
            mock_req.side_effect = [
                {"activity": [{"jnid": "a1"}, {"jnid": "a2"}], "count": 3},
                {"activity": [{"jnid": "a3"}], "count": 3},
            ]
            records = list(self.client.paginate_all("activities", page_size=2))
            assert [r["jnid"] for r in records] == ["a1", "a2", "a3"]


class TestFindRecord:
    def setup_method(self):
        self.client = JobNimbusClient(api_key="test-key")

    def test_find_in_contacts(self):
        with patch.object(self.client, "get_record") as mock_get:
            mock_get.return_value = {"jnid": "abc", "first_name": "John"}
            resource_type, record = self.client.find_record("abc")
            assert resource_type == "contacts"
            assert record["first_name"] == "John"

    def test_find_not_found(self):
        with patch.object(self.client, "get_record") as mock_get:
            mock_get.side_effect = JobNimbusClientError("Not found", status_code=404)
            resource_type, record = self.client.find_record("nonexistent")
            assert resource_type is None
            assert record is None

    def test_find_checks_multiple_resources(self):
        call_count = 0
        def mock_get(resource, record_id, fields=None):
            nonlocal call_count
            call_count += 1
            if resource == "jobs":
                return {"jnid": "xyz", "name": "A Job"}
            raise JobNimbusClientError("Not found", status_code=404)

        with patch.object(self.client, "get_record", side_effect=mock_get):
            resource_type, record = self.client.find_record("xyz")
            assert resource_type == "jobs"
            assert call_count >= 2  # Had to check contacts first


class TestGetRelated:
    def setup_method(self):
        self.client = JobNimbusClient(api_key="test-key")

    def test_related_for_contact(self):
        with patch.object(self.client, "list_records") as mock_list:
            mock_list.return_value = {"results": [{"jnid": "r1"}], "count": 1}
            related = self.client.get_related("contact123", resource_type="contact")
            assert "jobs" in related
            assert "tasks" in related
            assert "activities" in related
            assert "invoices" in related
            assert "estimates" in related

    def test_related_for_job(self):
        with patch.object(self.client, "list_records") as mock_list:
            mock_list.return_value = {"results": [], "count": 0}
            related = self.client.get_related("job456", resource_type="job")
            assert "tasks" in related
            assert "activities" in related
            assert "invoices" in related
            assert "estimates" in related
            # Jobs don't have nested jobs
            assert "jobs" not in related

    def test_related_handles_api_errors(self):
        with patch.object(self.client, "list_records") as mock_list:
            mock_list.side_effect = JobNimbusClientError("fail")
            related = self.client.get_related("x", resource_type="contact")
            for key in related:
                assert related[key]["count"] == 0


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


# ── CLI Subprocess Tests ────────────────────────────────────────────────────

class TestCLISubprocess:
    """Test the installed CLI command via subprocess."""

    @staticmethod
    def _resolve_cli(name="cli-anything-jobnimbus"):
        if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED"):
            import shutil
            path = shutil.which(name)
            if path:
                return [path]
            raise FileNotFoundError(f"{name} not found in PATH")
        return [sys.executable, "-m", "cli_anything.jobnimbus.jobnimbus_cli"]

    def test_version(self):
        result = subprocess.run(
            self._resolve_cli() + ["--version"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "0.2.0" in result.stdout

    def test_help(self):
        result = subprocess.run(
            self._resolve_cli() + ["--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "READ-ONLY" in result.stdout
        for cmd in ("contacts", "jobs", "tasks", "activities",
                    "invoices", "estimates", "products", "files",
                    "workflows", "find", "related", "export", "summary"):
            assert cmd in result.stdout, f"Missing command: {cmd}"

    def test_contacts_help(self):
        result = subprocess.run(
            self._resolve_cli() + ["contacts", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "list" in result.stdout
        assert "get" in result.stdout
        assert "search" in result.stdout

    def test_no_api_key_error(self):
        env = {k: v for k, v in os.environ.items() if k != "JOBNIMBUS_API_KEY"}
        result = subprocess.run(
            self._resolve_cli() + ["contacts", "list"],
            capture_output=True, text=True, timeout=10,
            env=env,
        )
        assert result.returncode != 0
