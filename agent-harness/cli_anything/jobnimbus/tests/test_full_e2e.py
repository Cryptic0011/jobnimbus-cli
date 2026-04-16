"""E2E tests for JobNimbus CLI — requires JOBNIMBUS_API_KEY env var.

These tests hit the real API and verify data integrity.
Skip if no API key is set.
"""

import json
import os
import subprocess
import sys
import time

import pytest

SKIP_REASON = "JOBNIMBUS_API_KEY not set — skipping E2E tests"
pytestmark = pytest.mark.skipif(
    not os.environ.get("JOBNIMBUS_API_KEY"),
    reason=SKIP_REASON,
)


def _resolve_cli():
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED"):
        import shutil
        path = shutil.which("cli-anything-jobnimbus") or shutil.which("jn")
        if path:
            return [path]
        raise FileNotFoundError("CLI not found in PATH")
    return [sys.executable, "-m", "cli_anything.jobnimbus.jobnimbus_cli"]


def run_cli(*args, json_mode=True):
    """Run CLI command and return parsed output."""
    cmd = _resolve_cli()
    if json_mode:
        cmd.append("--json")
    cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        pytest.fail(f"CLI failed: {result.stderr}\nstdout: {result.stdout}")
    if json_mode:
        return json.loads(result.stdout)
    return result.stdout


class TestE2EContacts:
    def test_list_contacts(self):
        data = run_cli("contacts", "list", "--size=5")
        assert "results" in data
        assert "count" in data
        assert isinstance(data["count"], int)
        assert len(data["results"]) <= 5

    def test_contact_has_expected_fields(self):
        data = run_cli("contacts", "list", "--size=1")
        if data["results"]:
            record = data["results"][0]
            assert "jnid" in record
            assert "date_created" in record

    def test_contact_timestamps_are_numeric(self):
        data = run_cli("contacts", "list", "--size=3")
        for record in data["results"]:
            if "date_created" in record and record["date_created"] is not None:
                ts = record["date_created"]
                assert isinstance(ts, (int, float)), \
                    f"date_created should be numeric, got {type(ts)}: {ts}"

    def test_contact_count(self):
        data = run_cli("contacts", "count")
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_contacts_pagination(self):
        page1 = run_cli("contacts", "list", "--size=2", "--offset=0")
        page2 = run_cli("contacts", "list", "--size=2", "--offset=2")
        if page1["count"] > 2:
            ids1 = {r["jnid"] for r in page1["results"]}
            ids2 = {r["jnid"] for r in page2["results"]}
            assert ids1.isdisjoint(ids2), "Pagination returned duplicate records"

    def test_contacts_fields_filter(self):
        data = run_cli("contacts", "list", "--size=2", "--fields=jnid,first_name")
        for record in data["results"]:
            assert "jnid" in record


class TestE2EJobs:
    def test_list_jobs(self):
        data = run_cli("jobs", "list", "--size=5")
        assert "results" in data
        assert "count" in data

    def test_job_has_expected_fields(self):
        data = run_cli("jobs", "list", "--size=1")
        if data["results"]:
            record = data["results"][0]
            assert "jnid" in record

    def test_job_timestamps_numeric(self):
        data = run_cli("jobs", "list", "--size=3")
        for record in data["results"]:
            if "date_created" in record and record["date_created"] is not None:
                assert isinstance(record["date_created"], (int, float))

    def test_jobs_sort_by_date_updated(self):
        data = run_cli("jobs", "list", "--size=5", "--sort-field=date_updated", "--sort-dir=desc")
        records = data["results"]
        if len(records) > 1:
            dates = [r.get("date_updated", 0) for r in records if r.get("date_updated")]
            assert dates == sorted(dates, reverse=True), "Jobs not sorted descending by date_updated"


class TestE2ETasks:
    def test_list_tasks(self):
        data = run_cli("tasks", "list", "--size=5")
        assert "results" in data
        assert "count" in data

    def test_task_timestamps_numeric(self):
        data = run_cli("tasks", "list", "--size=3")
        for record in data["results"]:
            if "date_created" in record and record["date_created"] is not None:
                assert isinstance(record["date_created"], (int, float))


class TestE2EActivities:
    def test_list_activities(self):
        data = run_cli("activities", "list", "--size=5")
        assert "results" in data
        assert "count" in data

    def test_activity_timestamps_numeric(self):
        data = run_cli("activities", "list", "--size=3")
        for record in data["results"]:
            if "date_created" in record and record["date_created"] is not None:
                assert isinstance(record["date_created"], (int, float))

    def test_activities_notes_shortcut(self):
        data = run_cli("activities", "notes", "--size=5")
        assert "results" in data


class TestE2EInvoices:
    def test_list_invoices(self):
        data = run_cli("invoices", "list", "--size=5")
        assert "results" in data
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_invoice_count(self):
        data = run_cli("invoices", "count")
        assert "count" in data


class TestE2EEstimates:
    def test_list_estimates(self):
        data = run_cli("estimates", "list", "--size=5")
        assert "results" in data
        assert "count" in data

    def test_estimate_count(self):
        data = run_cli("estimates", "count")
        assert "count" in data


class TestE2EProducts:
    def test_list_products(self):
        data = run_cli("products", "list", "--size=5")
        assert "results" in data or isinstance(data, list) or "count" in data


class TestE2EFiles:
    def test_list_files(self):
        data = run_cli("files", "list", "--size=5")
        assert "results" in data
        assert "count" in data


class TestE2EWorkflows:
    def test_workflows_returns_data(self):
        data = run_cli("workflows")
        assert isinstance(data, (dict, list))


class TestE2ESummary:
    def test_summary_json(self):
        data = run_cli("summary")
        assert "contacts" in data
        assert "jobs" in data
        assert "tasks" in data
        assert "activities" in data
        assert "invoices" in data
        assert "products" in data
        for key in ("contacts", "jobs", "tasks", "activities"):
            assert isinstance(data[key], (int, str))  # str for "n/a" on error


class TestE2EDataIntegrity:
    """Verify data returned is well-formed for agent consumption."""

    def test_jnid_format(self):
        """JNIDs should be non-empty strings."""
        data = run_cli("contacts", "list", "--size=5")
        for record in data["results"]:
            jnid = record.get("jnid")
            assert jnid is not None, "Record missing jnid"
            assert isinstance(jnid, str), f"jnid should be string, got {type(jnid)}"
            assert len(jnid) > 0, "jnid should not be empty"

    def test_timestamps_are_unix_epoch(self):
        """All timestamps should be reasonable Unix epoch values."""
        data = run_cli("contacts", "list", "--size=5")
        for record in data["results"]:
            for field in ("date_created", "date_updated"):
                val = record.get(field)
                if val is not None:
                    assert isinstance(val, (int, float)), \
                        f"{field} should be numeric, got {type(val)}"
                    # Should be between 2010 and 2030 in Unix time
                    assert 1262304000 < val < 1893456000, \
                        f"{field}={val} is outside reasonable range"

    def test_count_matches_or_exceeds_results(self):
        """count field should be >= len(results)."""
        data = run_cli("contacts", "list", "--size=5")
        assert data["count"] >= len(data["results"])

    def test_size_parameter_respected(self):
        """API should return at most 'size' records."""
        data = run_cli("contacts", "list", "--size=3")
        assert len(data["results"]) <= 3

    def test_json_output_is_valid(self):
        """--json output must be parseable JSON."""
        raw = run_cli("contacts", "list", "--size=1", json_mode=False)
        # Without --json, output should be human-readable (not JSON)
        # With --json flag it should be valid JSON
        data = run_cli("contacts", "list", "--size=1", json_mode=True)
        assert isinstance(data, dict)
