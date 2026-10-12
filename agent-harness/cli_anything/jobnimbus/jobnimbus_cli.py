"""JobNimbus CLI - agent-native read/write tool for a JobNimbus account.

Reads are always available. Writes (create / update / delete / upload) can be
previewed with --dry-run and blocked entirely with --read-only or
JOBNIMBUS_READ_ONLY=1.
"""

import cmd
import json
import shlex

import click

from cli_anything.jobnimbus import __version__
from cli_anything.jobnimbus.core.client import AuthenticationError, JobNimbusClientError
from cli_anything.jobnimbus.core.query import QueryError, build_filter
from cli_anything.jobnimbus.core.resources import RESOURCES
from cli_anything.jobnimbus.resource_commands import (
    data_options, emit, get_client, load_data, register_resources,
)
from cli_anything.jobnimbus.utils.formatting import format_json


class JobNimbusGroup(click.Group):
    """Root group: turns API and query errors into a clean one-line error."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except (JobNimbusClientError, QueryError) as e:
            raise click.ClickException(str(e))


@click.group(cls=JobNimbusGroup)
@click.option("--api-key", envvar="JOBNIMBUS_API_KEY", help="API key (or set JOBNIMBUS_API_KEY)")
@click.option("--json", "json_mode", is_flag=True, default=False, help="Output raw JSON")
@click.option("--dry-run", is_flag=True, default=False,
              help="Print the write request instead of sending it")
@click.option("--read-only", is_flag=True, default=False,
              help="Block all writes (also: JOBNIMBUS_READ_ONLY=1)")
@click.option("--actor", default=None, envvar="JOBNIMBUS_ACTOR",
              help="Act as this JobNimbus user (email); sets Created By on writes")
@click.version_option(version=__version__, prog_name="cli-anything-jobnimbus")
@click.pass_context
def cli(ctx, api_key, json_mode, dry_run, read_only, actor):
    """JobNimbus CLI — read and write everything in your JobNimbus account.

    \b
    Read:  list, get, count, search on every resource; find, related,
           export, summary, workflows.
    Write: create, update, delete (soft) on contacts, jobs, tasks,
           invoices, estimates, products, materialorders, workorders;
           activities create / add-note / update; files upload / update.
    Any other documented endpoint: jn api METHOD PATH.

    \b
    Safety: --dry-run previews a write; --read-only blocks all writes.

    Set JOBNIMBUS_API_KEY env var or use --api-key.
    """
    ctx.ensure_object(dict)
    ctx.obj.update(api_key=api_key, json_mode=json_mode, dry_run=dry_run,
                   read_only=read_only, actor=actor)


register_resources(cli)


# ── Workflows ───────────────────────────────────────────────────────────────

@cli.command("workflows")
@click.pass_context
def workflows_cmd(ctx):
    """Show all workflow definitions and pipeline statuses.

    With --json, returns the full account settings (workflows, custom fields,
    task/activity/file types, lead sources, locations).
    """
    result = get_client(ctx).get_account_settings()
    workflows = result.get("workflows") if isinstance(result, dict) else None
    if ctx.obj["json_mode"] or not isinstance(workflows, list):
        click.echo(format_json(result))
        return
    for wf in workflows:
        name = wf.get("name", "Unnamed")
        click.echo(f"\nWorkflow: {name}")
        click.echo("-" * (len(name) + 10))
        for status in wf.get("status") or wf.get("statuses") or []:
            click.echo(f"  - {status.get('name', '?')}")


# ── Cross-cutting: find / related ───────────────────────────────────────────

@cli.command("find")
@click.argument("record_id")
@click.pass_context
def find_cmd(ctx, record_id):
    """Find any record by JNID, auto-detecting its resource type."""
    resource_type, record = get_client(ctx).find_record(record_id)
    if resource_type is None:
        raise click.ClickException(f"Record '{record_id}' not found in any resource.")
    if ctx.obj["json_mode"]:
        click.echo(format_json({"resource_type": resource_type, "record": record}))
    else:
        click.echo(f"Found in: {resource_type}\n")
        emit(ctx, record, resource_type)


def _label(record):
    return (record.get("name") or record.get("title") or record.get("filename")
            or record.get("number") or (record.get("note") or "")[:60]
            or record.get("jnid", "?"))


@cli.command("related")
@click.argument("record_id")
@click.option("--type", "resource_type", type=click.Choice(["contact", "job"]),
              default=None, help="Record type (optional; 'job' skips the jobs lookup)")
@click.pass_context
def related_cmd(ctx, record_id, resource_type):
    """Pull the jobs, tasks, activities, invoices, estimates and files linked
    to a contact or job (up to 100 of each, newest first)."""
    related = get_client(ctx).get_related(record_id, resource_type=resource_type)
    if ctx.obj["json_mode"]:
        click.echo(format_json(related))
        return
    for rtype, data in related.items():
        click.echo(f"\n{rtype.upper()} ({data['count']})")
        click.echo("=" * 40)
        for record in data["results"][:10]:
            click.echo(f"  {record.get('jnid', '?')}: {_label(record)}")
        if data["count"] > 10:
            click.echo(f"  ... and {data['count'] - 10} more")
        if not data["results"]:
            click.echo("  (none)")


# ── Cross-cutting: export / summary ─────────────────────────────────────────

@cli.command("export")
@click.argument("resource", type=click.Choice(list(RESOURCES)))
@click.option("--max", "max_records", type=int, default=None, help="Max records to export (default: all)")
@click.option("--fields", default=None, help="Comma-separated fields to include")
@click.option("--query", "-q", default=None, help="Query to filter, e.g. 'record_type_name:Note'")
@click.option("--filter", "raw_filter", default=None, help="Raw JobNimbus filter JSON")
@click.option("--sort-field", default="date_updated", show_default=True,
              help="Field to sort by (must be a date/number to export past 10,000 records)")
@click.option("--sort-dir", type=click.Choice(["asc", "desc"]), default="desc", show_default=True)
@click.pass_context
def export_cmd(ctx, resource, max_records, fields, query, raw_filter, sort_field, sort_dir):
    """Export all records of a type as JSONL (one JSON object per line).

    \b
    Examples:
      jn export contacts > contacts.jsonl
      jn export activities --query="record_type_name:Note" --fields=note,jnid
      jn export jobs --max=500 --sort-field=date_created
    """
    count = 0
    for record in get_client(ctx).paginate_all(
        resource, page_size=1000, sort_field=sort_field, sort_direction=sort_dir,
        filter=build_filter(query, raw_filter), fields=fields, max_records=max_records,
    ):
        click.echo(json.dumps(record, default=str, ensure_ascii=False))
        count += 1
    click.echo(f"\nExported {count} {resource}.", err=True)


@cli.command("summary")
@click.pass_context
def summary(ctx):
    """Show account overview with record counts for ALL resources."""
    client = get_client(ctx)
    counts = {}
    for resource in RESOURCES:
        try:
            counts[resource] = client.count_records(resource)
        except AuthenticationError:
            raise
        except JobNimbusClientError:
            counts[resource] = "n/a"

    if ctx.obj["json_mode"]:
        click.echo(format_json(counts))
        return
    click.echo("Account Summary")
    click.echo("=" * 30)
    for resource, count in counts.items():
        click.echo(f"  {resource.capitalize():15s} {count}")


# ── Raw API access ──────────────────────────────────────────────────────────

@cli.command("api")
@click.argument("method", type=click.Choice(["GET", "POST", "PUT"], case_sensitive=False))
@click.argument("path")
@click.option("--param", "-p", "params", multiple=True, metavar="KEY=VALUE",
              help="Query string parameter (repeatable)")
@data_options
@click.pass_context
def api_cmd(ctx, method, path, params, data, sets):
    """Call any JobNimbus endpoint directly.

    PATH is relative to https://app.jobnimbus.com/api1/ (or a full
    https://*.jobnimbus.com URL). Covers endpoints without a dedicated
    command: users, UoMs, payments, and account setup.

    \b
    Examples:
      jn api GET account/users
      jn api GET utility/uoms
      jn api POST account/leadsource --set SourceName=Google
      jn api POST account/workflow/12/status --set name="On Hold"
      jn api POST https://app.jobnimbus.com/api2/v2/payments --data @payment.json
    """
    query = {}
    for item in params:
        key, sep, value = item.partition("=")
        if not sep:
            raise click.UsageError(f"--param expects KEY=VALUE, got '{item}'.")
        query[key] = value
    body = load_data(data, sets, required=False) or None
    result = get_client(ctx)._request(method, path, params=query, body=body)
    click.echo(result if isinstance(result, str) else format_json(result))


# ── REPL ────────────────────────────────────────────────────────────────────

class JobNimbusREPL(cmd.Cmd):
    """Interactive REPL: every line is run as a `jn` command."""

    intro = "JobNimbus REPL — type any jn command (e.g. 'contacts list -s 5'), 'json' to toggle JSON, 'quit' to exit.\n"
    prompt = "jn> "

    def __init__(self, base_args=(), json_mode=False):
        super().__init__()
        self.base_args = list(base_args)
        self.json_mode = json_mode

    def default(self, line):
        try:
            args = shlex.split(line)
        except ValueError as e:
            click.echo(f"Parse error: {e}")
            return
        prefix = self.base_args + (["--json"] if self.json_mode else [])
        try:
            cli.main(prefix + args, prog_name="jn", standalone_mode=False, obj={})
        except click.ClickException as e:
            e.show()
        except (click.Abort, SystemExit):
            pass

    def emptyline(self):
        """Do nothing (the cmd default re-runs the last command, which could repeat a write)."""

    def do_help(self, line):
        """Show help for a command."""
        self.default(f"{line} --help")

    def do_json(self, line):
        """Toggle JSON output mode."""
        self.json_mode = not self.json_mode
        click.echo(f"JSON mode: {'ON' if self.json_mode else 'OFF'}")

    def do_quit(self, line):
        """Exit the REPL."""
        return True

    do_exit = do_EOF = do_quit


@cli.command("repl")
@click.pass_context
def repl_cmd(ctx):
    """Start interactive REPL session."""
    obj = ctx.obj
    base_args = (
        (["--api-key", obj["api_key"]] if obj.get("api_key") else [])
        + (["--dry-run"] if obj.get("dry_run") else [])
        + (["--read-only"] if obj.get("read_only") else [])
        + (["--actor", obj["actor"]] if obj.get("actor") else [])
    )
    try:
        JobNimbusREPL(base_args=base_args, json_mode=obj["json_mode"]).cmdloop()
    except KeyboardInterrupt:
        click.echo("\nExiting REPL.")


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    cli(obj={}, prog_name="jn")


if __name__ == "__main__":
    main()
