"""Per-resource command groups, generated from the resource table."""

import json
import os
import sys

import click

from cli_anything.jobnimbus.core.client import JobNimbusClient
from cli_anything.jobnimbus.core.query import build_filter, merge_filters
from cli_anything.jobnimbus.core.resources import CREATE, DELETE, RESOURCES, UPDATE
from cli_anything.jobnimbus.utils.formatting import format_json, output_results


def get_client(ctx):
    """Get or create the API client from Click context."""
    obj = ctx.obj
    if "client" not in obj:
        obj["client"] = JobNimbusClient(
            api_key=obj.get("api_key"),
            actor=obj.get("actor"),
            read_only=True if obj.get("read_only") else None,
            dry_run=obj.get("dry_run", False),
        )
    return obj["client"]


def emit(ctx, result, resource=None, columns=None):
    """Print an API result: raw JSON in --json mode (and for dry runs), else a summary."""
    is_dry_run = isinstance(result, dict) and result.get("dry_run")
    if ctx.obj["json_mode"] or is_dry_run or not isinstance(result, (dict, list)):
        click.echo(result if isinstance(result, str) else format_json(result))
    else:
        output_results(result, resource_type=resource, columns=columns)


# ── Write payloads ──────────────────────────────────────────────────────────

def data_options(f):
    f = click.option(
        "--set", "sets", multiple=True, metavar="KEY=VALUE",
        help="Set one field (repeatable). Dotted keys nest (primary.id=abc). "
             "KEY=VALUE is a string; KEY:=VALUE is raw JSON (count:=3, done:=true).",
    )(f)
    f = click.option(
        "--data", "-d", default=None,
        help="JSON object body: inline, @file.json, or - for stdin.",
    )(f)
    return f


def _set_path(obj, keys, value):
    head, *rest = keys
    if not rest:
        return {**obj, head: value}
    child = obj.get(head) if isinstance(obj.get(head), dict) else {}
    return {**obj, head: _set_path(child, rest, value)}


def load_data(data, sets, required=True):
    """Build the request body from --data and --set."""
    payload = {}
    if data:
        if data == "-":
            text = sys.stdin.read()
        elif data.startswith("@"):
            with open(data[1:]) as fh:
                text = fh.read()
        else:
            text = data
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as e:
            raise click.UsageError(f"--data is not valid JSON: {e}")
        if not isinstance(payload, dict):
            raise click.UsageError("--data must be a JSON object.")
    for item in sets:
        key, sep, raw = item.partition("=")
        if not sep or not key.rstrip(":"):
            raise click.UsageError(f"--set expects KEY=VALUE, got '{item}'.")
        value = raw
        if key.endswith(":"):
            key = key[:-1]
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as e:
                raise click.UsageError(f"--set {key}:= needs a JSON value: {e}")
        payload = _set_path(payload, key.split("."), value)
    if required and not payload:
        raise click.UsageError("Nothing to send. Provide --data and/or --set.")
    return payload


# ── Generated commands ──────────────────────────────────────────────────────

def _filter_options(res):
    def decorator(f):
        for option, api_field in res.filters.items():
            f = click.option(f"--{option}", default=None, help=f"Filter: {api_field} equals value")(f)
        f = click.option("--filter", "raw_filter", default=None,
                         help='Raw JobNimbus filter JSON, e.g. \'{"must":[{"term":{"city":"Orlando"}}]}\'')(f)
        return f
    return decorator


def _list_options(f):
    f = click.option("--size", "-s", type=int, default=50, help="Records per page (max 1000)")(f)
    f = click.option("--offset", "-o", type=int, default=0, help="Starting index (0-based, max 9999)")(f)
    f = click.option("--sort-field", default="date_updated", show_default=True, help="Field to sort by")(f)
    f = click.option("--sort-dir", type=click.Choice(["asc", "desc"]), default="desc", show_default=True)(f)
    f = click.option("--fields", default=None, help="Comma-separated fields to return")(f)
    f = click.option("--columns", default=None, help="Comma-separated columns for table output")(f)
    return f


def _named_terms(res, named):
    """Map --status style option values onto (api_field, value) pairs."""
    return [
        (api_field, named.get(option.replace("-", "_")))
        for option, api_field in res.filters.items()
    ]


def _add_read_commands(group, name, res):
    def run_list(ctx, query, raw_filter, size, offset, sort_field, sort_dir, fields, columns, **named):
        result = get_client(ctx).list_records(
            name, size=size, offset=offset, sort_field=sort_field, sort_direction=sort_dir,
            fields=fields, filter=build_filter(query, raw_filter, _named_terms(res, named)),
        )
        emit(ctx, result, name, columns.split(",") if columns else None)

    @group.command("list", help=f"List {name} with optional filtering and pagination.")
    @_list_options
    @click.option("--query", "-q", default=None, help="Query, e.g. 'city:Orlando AND status_name:Lead'")
    @_filter_options(res)
    @click.pass_context
    def list_cmd(ctx, **kwargs):
        run_list(ctx, **kwargs)

    @group.command("search", help=f"Search {name}: field:value, field:*wild*, field:[lo TO hi], AND / OR / NOT.")
    @click.argument("query")
    @_list_options
    @_filter_options(res)
    @click.pass_context
    def search_cmd(ctx, **kwargs):
        run_list(ctx, **kwargs)

    @group.command("count", help=f"Count {name} matching an optional query.")
    @click.option("--query", "-q", default=None, help="Query, e.g. 'status_name:Lead'")
    @_filter_options(res)
    @click.pass_context
    def count_cmd(ctx, query, raw_filter, **named):
        count = get_client(ctx).count_records(
            name, filter=build_filter(query, raw_filter, _named_terms(res, named)),
        )
        if ctx.obj["json_mode"]:
            click.echo(format_json({"resource": name, "count": count}))
        else:
            click.echo(f"{name.capitalize()}: {count}")

    @group.command("get", help=f"Get a single {name} record by JNID.")
    @click.argument("record_id")
    @click.option("--fields", default=None, help="Comma-separated fields to return")
    @click.pass_context
    def get_cmd(ctx, record_id, fields):
        emit(ctx, get_client(ctx).get_record(name, record_id, fields=fields), name)


def _add_write_commands(group, name, res):
    if CREATE in res.writes:
        @group.command("create", help=f"Create a {name} record (POST).")
        @data_options
        @click.pass_context
        def create_cmd(ctx, data, sets):
            emit(ctx, get_client(ctx).create_record(name, load_data(data, sets)), name)

    if UPDATE in res.writes:
        @group.command("update", help=f"Update fields on a {name} record (PUT). Only the fields sent change.")
        @click.argument("record_id")
        @data_options
        @click.pass_context
        def update_cmd(ctx, record_id, data, sets):
            emit(ctx, get_client(ctx).update_record(name, record_id, load_data(data, sets)), name)

    if DELETE in res.writes:
        @group.command("delete", help=f"Soft-delete a {name} record (sets is_active=false). "
                                      "Undo with: update ID --set is_active:=true")
        @click.argument("record_id")
        @click.option("--yes", is_flag=True, help="Confirm the delete (required).")
        @click.pass_context
        def delete_cmd(ctx, record_id, yes):
            if not (yes or ctx.obj.get("dry_run")):
                raise click.UsageError(f"Refusing to delete {name} {record_id} without --yes.")
            emit(ctx, get_client(ctx).delete_record(name, record_id), name)


def _add_activity_commands(group):
    @group.command("notes")
    @click.option("--size", "-s", type=int, default=50, help="Records per page")
    @click.option("--offset", "-o", type=int, default=0, help="Starting index")
    @click.option("--contact-id", default=None, help="Filter by contact JNID")
    @click.option("--job-id", default=None, help="Filter by job JNID")
    @click.option("--search", default=None, help="Text to find within the note")
    @click.pass_context
    def notes_cmd(ctx, size, offset, contact_id, job_id, search):
        """List note activities, newest first (note, date, author only)."""
        terms = [("record_type_name", "Note"), ("related.id", contact_id), ("related.id", job_id)]
        note_filter = build_filter(terms=terms)
        if search:
            note_filter = merge_filters(note_filter, {"must": [{"wildcard": {"note": f"*{search}*"}}]})
        result = get_client(ctx).list_records(
            "activities", size=size, offset=offset,
            sort_field="date_created", sort_direction="desc",
            fields="note,date_created,jnid,created_by_name", filter=note_filter,
        )
        emit(ctx, result, "activities")

    @group.command("add-note")
    @click.argument("record_id")
    @click.argument("text")
    @click.option("--type", "note_type", default="Note", show_default=True,
                  help="Activity type name from the account settings")
    @click.pass_context
    def add_note_cmd(ctx, record_id, text, note_type):
        """Add a note to a contact or job: jn activities add-note JNID "text"."""
        body = {"note": text, "record_type_name": note_type, "primary": {"id": record_id}}
        emit(ctx, get_client(ctx).create_record("activities", body), "activities")


def _add_file_commands(group):
    @group.command("download")
    @click.argument("file_id")
    @click.option("--output", "-o", default=None, help="Destination path (default: the file's own name)")
    @click.option("--force", is_flag=True, help="Overwrite an existing file")
    @click.pass_context
    def download_cmd(ctx, file_id, output, force):
        """Download a file attachment's content."""
        client = get_client(ctx)
        if not output:
            meta = client.get_record("files", file_id, fields="jnid,filename")
            # The filename comes from the CRM: keep only its last path component.
            output = os.path.basename(meta.get("filename") or "") or file_id
        if os.path.exists(output) and not force:
            raise click.UsageError(f"'{output}' already exists. Use --force or --output.")
        size = client.download_file(file_id, output)
        result = {"jnid": file_id, "path": os.path.abspath(output), "bytes": size}
        click.echo(format_json(result) if ctx.obj["json_mode"] else f"Saved {size} bytes to {result['path']}")

    @group.command("upload")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    @click.option("--related", multiple=True, required=True, help="Contact/job JNID to attach to (repeatable)")
    @click.option("--type", "file_type", type=int, default=1, show_default=True,
                  help="1=Document 2=Photo 3=Email Attachment 5=Invoice, or a custom type id")
    @click.option("--description", default=None)
    @click.option("--filename", default=None, help="Name to store (default: local file name)")
    @click.option("--private", "is_private", is_flag=True)
    @click.pass_context
    def upload_cmd(ctx, path, related, file_type, description, filename, is_private):
        """Upload a local file (<100MB) and attach it to contacts or jobs."""
        emit(ctx, get_client(ctx).upload_file(
            path, related, file_type=file_type, description=description,
            filename=filename, is_private=is_private,
        ), "files")


def register_resources(cli):
    """Attach one command group per resource to the root CLI."""
    for name, res in RESOURCES.items():
        group = click.Group(name, help=res.help)
        _add_read_commands(group, name, res)
        _add_write_commands(group, name, res)
        if name == "activities":
            _add_activity_commands(group)
        if name == "files":
            _add_file_commands(group)
        cli.add_command(group)
