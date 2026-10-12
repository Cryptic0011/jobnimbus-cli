"""CLI tests — the HTTP layer is mocked, nothing touches the network."""

import json
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from cli_anything.jobnimbus import __version__
from cli_anything.jobnimbus.core.client import JobNimbusClient
from cli_anything.jobnimbus.jobnimbus_cli import JobNimbusREPL, cli
from cli_anything.jobnimbus.resource_commands import load_data
from cli_anything.jobnimbus.tests.test_core import make_response


@pytest.fixture
def api(monkeypatch):
    """Mock of requests.Session.request shared by every client the CLI builds."""
    monkeypatch.setenv("JOBNIMBUS_API_KEY", "test-key")
    monkeypatch.delenv("JOBNIMBUS_READ_ONLY", raising=False)
    monkeypatch.delenv("JOBNIMBUS_ACTOR", raising=False)
    mock = MagicMock(return_value=make_response(body={"results": [], "count": 0}))
    monkeypatch.setattr("cli_anything.jobnimbus.core.client.requests.Session.request", mock)
    return mock


def run(*args, input=None):
    return CliRunner().invoke(cli, list(args), obj={}, input=input)


def request(api, index=-1):
    args, kwargs = api.call_args_list[index]
    return args[0], args[1], kwargs


class TestLoadData:
    def test_set_strings_json_and_nesting(self):
        assert load_data(None, ("zip=32806", "primary.id=abc", "primary.type=contact",
                                "is_active:=true", "tags:=[1,2]", "note=a=b")) == {
            "zip": "32806",  # stays a string: zip codes and record numbers are not numbers
            "primary": {"id": "abc", "type": "contact"},
            "is_active": True,
            "tags": [1, 2],
            "note": "a=b",
        }

    def test_set_overrides_data(self):
        assert load_data('{"a": 1, "b": {"c": 2}}', ("b.d=x",)) == {"a": 1, "b": {"c": 2, "d": "x"}}

    def test_data_from_file(self, tmp_path):
        path = tmp_path / "body.json"
        path.write_text('{"name": "X"}')
        assert load_data(f"@{path}", ()) == {"name": "X"}

    @pytest.mark.parametrize("data,sets", [
        (None, ()), ("{bad", ()), ("[1]", ()), (None, ("novalue",)), (None, ("n:=notjson",)),
    ])
    def test_rejects_bad_input(self, data, sets):
        with pytest.raises(click.UsageError):
            load_data(data, sets)


class TestReadCommands:
    def test_help_lists_every_command(self):
        out = run("--help").output
        for name in ("contacts", "jobs", "tasks", "activities", "invoices", "estimates",
                     "products", "materialorders", "workorders", "files", "payments",
                     "creditmemos", "workflows", "find", "related", "export", "summary",
                     "api", "repl"):
            assert name in out, f"Missing command: {name}"

    def test_version(self):
        assert __version__ in run("--version").output

    def test_missing_api_key_is_a_clean_error(self, monkeypatch):
        monkeypatch.delenv("JOBNIMBUS_API_KEY", raising=False)
        result = run("contacts", "list")
        assert result.exit_code == 1
        assert "No API key" in result.output

    def test_list_filters_reach_the_api(self, api):
        result = run("--json", "jobs", "list", "--status", "Lead", "--contact-id", "c1",
                     "-q", "city:Orlando", "--size", "5")
        assert result.exit_code == 0, result.output
        params = request(api)[2]["params"]
        assert json.loads(params["filter"]) == {"must": [
            {"term": {"city": "Orlando"}},
            {"term": {"status_name": "Lead"}},
            {"term": {"primary.id": "c1"}},
        ]}
        assert params["size"] == 5

    def test_search_and_count_send_the_query(self, api):
        run("contacts", "search", "status_name:Lead")
        assert "status_name" in request(api)[2]["params"]["filter"]
        result = run("--json", "contacts", "count", "-q", "status_name:Lead")
        assert json.loads(result.output) == {"resource": "contacts", "count": 0}
        assert "status_name" in request(api)[2]["params"]["filter"]

    def test_bad_query_fails_loudly_without_calling_the_api(self, api):
        result = run("contacts", "search", "city:Orlando AND (a:b OR c:d)")
        assert result.exit_code == 1
        assert "Cannot parse query" in result.output
        api.assert_not_called()

    def test_api_error_is_one_line_not_a_traceback(self, api):
        api.return_value = make_response(404, text="This record could not be found")
        result = run("contacts", "get", "bogus")
        assert result.exit_code == 1
        assert result.output.strip() == "Error: API error 404: This record could not be found"

    def test_notes_filters_on_note_type_and_text(self, api):
        run("activities", "notes", "--job-id", "j1", "--search", "roof leak")
        assert json.loads(request(api)[2]["params"]["filter"]) == {"must": [
            {"term": {"record_type_name": "Note"}},
            {"term": {"related.id": "j1"}},
            {"wildcard": {"note": "*roof leak*"}},
        ]}

    def test_export_writes_jsonl(self, api):
        api.return_value = make_response(body={"results": [{"jnid": "a"}, {"jnid": "b"}], "count": 2})
        result = run("export", "contacts", "--fields", "jnid")
        lines = [json.loads(line) for line in result.stdout.strip().splitlines()]
        assert lines == [{"jnid": "a"}, {"jnid": "b"}]


class TestWriteCommands:
    def test_create(self, api):
        api.return_value = make_response(body={"jnid": "new1", "first_name": "Sam"})
        result = run("--json", "contacts", "create", "--set", "first_name=Sam",
                     "--set", "status_name=Lead")
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["jnid"] == "new1"
        method, url, kwargs = request(api)
        assert (method, url) == ("POST", f"{JobNimbusClient.BASE_URL}/contacts")
        assert kwargs["json"] == {"first_name": "Sam", "status_name": "Lead"}

    def test_update_from_stdin(self, api):
        run("jobs", "update", "j1", "--data", "-", input='{"status_name": "Completed"}')
        method, url, kwargs = request(api)
        assert (method, url) == ("PUT", f"{JobNimbusClient.BASE_URL}/jobs/j1")
        assert kwargs["json"] == {"status_name": "Completed"}

    def test_update_without_fields_sends_nothing(self, api):
        assert run("contacts", "update", "c1").exit_code == 2
        api.assert_not_called()

    def test_delete_requires_yes(self, api):
        result = run("contacts", "delete", "c1")
        assert result.exit_code == 2 and "--yes" in result.output
        api.assert_not_called()
        assert run("contacts", "delete", "c1", "--yes").exit_code == 0
        assert request(api)[2]["json"] == {"is_active": False}

    def test_add_note(self, api):
        run("activities", "add-note", "c1", "Left a voicemail")
        method, url, kwargs = request(api)
        assert (method, url) == ("POST", f"{JobNimbusClient.BASE_URL}/activities")
        assert kwargs["json"] == {"note": "Left a voicemail", "record_type_name": "Note",
                                  "primary": {"id": "c1"}}

    def test_dry_run_prints_request_and_sends_nothing(self, api):
        result = run("--dry-run", "--actor", "sam@company.com", "tasks", "create",
                     "--set", "title=Call back")
        preview = json.loads(result.output)
        assert preview["method"] == "POST" and preview["body"] == {"title": "Call back"}
        assert preview["params"] == {"actor": "sam@company.com"}
        api.assert_not_called()

    def test_read_only_flag_and_env_block_writes(self, api, monkeypatch):
        result = run("--read-only", "contacts", "update", "c1", "--set", "zip=1")
        assert result.exit_code == 1 and "read-only" in result.output
        monkeypatch.setenv("JOBNIMBUS_READ_ONLY", "1")
        assert run("activities", "add-note", "c1", "x").exit_code == 1
        assert run("api", "POST", "account/leadsource", "--set", "SourceName=G").exit_code == 1
        api.assert_not_called()
        assert run("contacts", "count").exit_code == 0  # reads still allowed

    def test_unsupported_writes_have_no_command(self, api):
        for args in (("activities", "delete", "a1", "--yes"),
                     ("files", "create", "--set", "a=b"),
                     ("payments", "delete", "p1", "--yes")):
            assert run(*args).exit_code == 2
        api.assert_not_called()

    def test_activities_and_files_can_be_updated(self, api):
        run("files", "update", "f1", "--set", 'related:=["c1"]')
        method, url, kwargs = request(api)
        assert (method, url) == ("PUT", f"{JobNimbusClient.BASE_URL}/files/f1")
        assert kwargs["json"] == {"related": ["c1"]}
        run("activities", "update", "a1", "--set", "note=fixed typo")
        assert request(api)[:2] == ("PUT", f"{JobNimbusClient.BASE_URL}/activities/a1")

    def test_raw_api_command(self, api):
        run("api", "POST", "account/workflow/12/status", "--set", "name=On Hold",
            "--param", "x=1")
        method, url, kwargs = request(api)
        assert (method, url) == ("POST", f"{JobNimbusClient.BASE_URL}/account/workflow/12/status")
        assert kwargs["json"] == {"name": "On Hold"} and kwargs["params"] == {"x": "1"}


class TestRepl:
    def test_quoted_args_and_json_toggle(self, api, capsys):
        repl = JobNimbusREPL()
        repl.onecmd('contacts count -q \'status_name:"Appointment Booked"\'')
        assert "Appointment Booked" in request(api)[2]["params"]["filter"]
        repl.onecmd("json")
        capsys.readouterr()
        repl.onecmd("contacts count")
        assert json.loads(capsys.readouterr().out) == {"resource": "contacts", "count": 0}

    def test_empty_line_does_not_repeat_a_write(self, api):
        repl = JobNimbusREPL()
        repl.onecmd("activities add-note c1 hello")
        repl.onecmd(repl.precmd(""))
        assert api.call_count == 1

    def test_errors_do_not_exit_the_repl(self, api, capsys):
        JobNimbusREPL().onecmd("contacts delete c1")
        assert "--yes" in capsys.readouterr().err
