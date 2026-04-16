"""JobNimbus Read-Only CLI - Agent-native reporting tool.

STRICT READ-ONLY: This CLI only implements GET operations.
No data is ever created, modified, or deleted.
"""

import sys
import json
import os
import cmd

import click

from cli_anything.jobnimbus.core.client import (
    JobNimbusClient,
    JobNimbusClientError,
    AuthenticationError,
)
from cli_anything.jobnimbus.utils.formatting import (
    format_json,
    format_table,
    output_results,
    unix_to_iso,
)


def get_client(ctx):
    """Get or create the API client from Click context."""
    if "client" not in ctx.obj:
        try:
            ctx.obj["client"] = JobNimbusClient(api_key=ctx.obj.get("api_key"))
        except AuthenticationError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    return ctx.obj["client"]


# ── Shared options ──────────────────────────────────────────────────────────

def common_list_options(f):
    """Decorator for shared list command options."""
    f = click.option("--size", "-s", type=int, default=50, help="Records per page (max 1000)")(f)
    f = click.option("--offset", "-o", type=int, default=0, help="Starting index (0-based)")(f)
    f = click.option("--sort-field", type=str, default=None, help="Field to sort by")(f)
    f = click.option("--sort-dir", type=click.Choice(["asc", "desc"]), default=None, help="Sort direction")(f)
    f = click.option("--query", "-q", type=str, default=None, help="ElasticSearch query string")(f)
    f = click.option("--fields", type=str, default=None, help="Comma-separated fields to return")(f)
    f = click.option("--columns", type=str, default=None, help="Comma-separated columns for table output")(f)
    return f


# ── Root CLI ────────────────────────────────────────────────────────────────

@click.group()
@click.option("--api-key", envvar="JOBNIMBUS_API_KEY", help="API key (or set JOBNIMBUS_API_KEY)")
@click.option("--json", "json_mode", is_flag=True, default=False, help="Output raw JSON")
@click.version_option(version="0.2.0", prog_name="cli-anything-jobnimbus")
@click.pass_context
def cli(ctx, api_key, json_mode):
    """JobNimbus Read-Only CLI — audit everything in your JobNimbus account.

    \b
    STRICT READ-ONLY: Only GET operations are supported.
    No data is ever created, modified, or deleted.

    Resources: contacts, jobs, tasks, activities, invoices,
    estimates, products, files, workflows.

    Set JOBNIMBUS_API_KEY env var or use --api-key.
    """
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["json_mode"] = json_mode


# ── Contacts ────────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def contacts(ctx):
    """Read contacts (customers, leads, etc.)."""
    pass


@contacts.command("list")
@common_list_options
@click.option("--status", type=str, default=None, help="Filter by status name")
@click.option("--type", "contact_type", type=str, default=None, help="Filter by contact type")
@click.pass_context
def contacts_list(ctx, size, offset, sort_field, sort_dir, query, fields, columns,
                  status, contact_type):
    """List contacts with optional filtering and pagination."""
    client = get_client(ctx)
    filters = {}
    if status:
        filters["status"] = status
    if contact_type:
        filters["contact_type"] = contact_type

    result = client.list_records(
        "contacts", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields, filters=filters,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="contacts", columns=col_list)


@contacts.command("get")
@click.argument("record_id")
@click.option("--fields", type=str, default=None, help="Comma-separated fields to return")
@click.pass_context
def contacts_get(ctx, record_id, fields):
    """Get a single contact by JNID."""
    client = get_client(ctx)
    result = client.get_record("contacts", record_id, fields=fields)
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="contacts")


@contacts.command("count")
@click.option("--query", "-q", type=str, default=None, help="ElasticSearch query string")
@click.pass_context
def contacts_count(ctx, query):
    """Count contacts matching an optional query."""
    client = get_client(ctx)
    count = client.count_records("contacts", query=query)
    if ctx.obj["json_mode"]:
        print(format_json({"resource": "contacts", "count": count}))
    else:
        click.echo(f"Contacts: {count}")


@contacts.command("search")
@click.argument("query")
@common_list_options
@click.pass_context
def contacts_search(ctx, query, size, offset, sort_field, sort_dir, fields, columns, **_):
    """Search contacts using ElasticSearch query syntax.

    \b
    Examples:
      jn contacts search "first_name:John"
      jn contacts search "status_name:Lead"
      jn contacts search "city:Miami AND state_text:FL"
    """
    client = get_client(ctx)
    result = client.list_records(
        "contacts", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="contacts", columns=col_list)


# ── Jobs ────────────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def jobs(ctx):
    """Read jobs (projects, work orders, etc.)."""
    pass


@jobs.command("list")
@common_list_options
@click.option("--status", type=str, default=None, help="Filter by status name")
@click.option("--type", "job_type", type=str, default=None, help="Filter by job type")
@click.option("--contact-id", type=str, default=None, help="Filter by primary contact JNID")
@click.pass_context
def jobs_list(ctx, size, offset, sort_field, sort_dir, query, fields, columns,
              status, job_type, contact_id):
    """List jobs with optional filtering and pagination."""
    client = get_client(ctx)
    filters = {}
    if status:
        filters["status"] = status
    if job_type:
        filters["job_type"] = job_type
    if contact_id:
        filters["primary_id"] = contact_id

    result = client.list_records(
        "jobs", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields, filters=filters,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="jobs", columns=col_list)


@jobs.command("get")
@click.argument("record_id")
@click.option("--fields", type=str, default=None, help="Comma-separated fields to return")
@click.pass_context
def jobs_get(ctx, record_id, fields):
    """Get a single job by JNID."""
    client = get_client(ctx)
    result = client.get_record("jobs", record_id, fields=fields)
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="jobs")


@jobs.command("count")
@click.option("--query", "-q", type=str, default=None, help="ElasticSearch query string")
@click.pass_context
def jobs_count(ctx, query):
    """Count jobs matching an optional query."""
    client = get_client(ctx)
    count = client.count_records("jobs", query=query)
    if ctx.obj["json_mode"]:
        print(format_json({"resource": "jobs", "count": count}))
    else:
        click.echo(f"Jobs: {count}")


@jobs.command("search")
@click.argument("query")
@common_list_options
@click.pass_context
def jobs_search(ctx, query, size, offset, sort_field, sort_dir, fields, columns, **_):
    """Search jobs using ElasticSearch query syntax.

    \b
    Examples:
      jn jobs search "status_name:Completed"
      jn jobs search "record_type_name:Roof"
      jn jobs search "name:*Smith*"
    """
    client = get_client(ctx)
    result = client.list_records(
        "jobs", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="jobs", columns=col_list)


# ── Tasks ───────────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def tasks(ctx):
    """Read tasks (to-dos, assignments)."""
    pass


@tasks.command("list")
@common_list_options
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--assignee", type=str, default=None, help="Filter by assignee")
@click.option("--contact-id", type=str, default=None, help="Filter by related contact JNID")
@click.option("--job-id", type=str, default=None, help="Filter by related job JNID")
@click.pass_context
def tasks_list(ctx, size, offset, sort_field, sort_dir, query, fields, columns,
               status, assignee, contact_id, job_id):
    """List tasks with optional filtering and pagination."""
    client = get_client(ctx)
    filters = {}
    if status:
        filters["status"] = status
    if assignee:
        filters["assignee"] = assignee
    if contact_id:
        filters["related_contact"] = contact_id
    if job_id:
        filters["related_job"] = job_id

    result = client.list_records(
        "tasks", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields, filters=filters,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="tasks", columns=col_list)


@tasks.command("get")
@click.argument("record_id")
@click.option("--fields", type=str, default=None, help="Comma-separated fields to return")
@click.pass_context
def tasks_get(ctx, record_id, fields):
    """Get a single task by JNID."""
    client = get_client(ctx)
    result = client.get_record("tasks", record_id, fields=fields)
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="tasks")


@tasks.command("count")
@click.option("--query", "-q", type=str, default=None, help="ElasticSearch query string")
@click.pass_context
def tasks_count(ctx, query):
    """Count tasks matching an optional query."""
    client = get_client(ctx)
    count = client.count_records("tasks", query=query)
    if ctx.obj["json_mode"]:
        print(format_json({"resource": "tasks", "count": count}))
    else:
        click.echo(f"Tasks: {count}")


@tasks.command("search")
@click.argument("query")
@common_list_options
@click.pass_context
def tasks_search(ctx, query, size, offset, sort_field, sort_dir, fields, columns, **_):
    """Search tasks using ElasticSearch query syntax.

    \b
    Examples:
      jn tasks search "status:Open"
      jn tasks search "title:*inspection*"
      jn tasks search "priority:high"
    """
    client = get_client(ctx)
    result = client.list_records(
        "tasks", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="tasks", columns=col_list)


# ── Activities ──────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def activities(ctx):
    """Read activities (notes, emails, calls, audit trail)."""
    pass


@activities.command("list")
@common_list_options
@click.option("--type", "activity_type", type=str, default=None,
              help="Filter by type (note, email, call, etc.)")
@click.option("--contact-id", type=str, default=None, help="Filter by related contact JNID")
@click.option("--job-id", type=str, default=None, help="Filter by related job JNID")
@click.pass_context
def activities_list(ctx, size, offset, sort_field, sort_dir, query, fields, columns,
                    activity_type, contact_id, job_id):
    """List activities with optional filtering and pagination.

    Activities include notes, emails, calls, and system events.
    Use --fields=note,date_created for token-efficient note scraping.
    """
    client = get_client(ctx)
    filters = {}
    if activity_type:
        filters["record_type_name"] = activity_type
    if contact_id:
        filters["primary_id"] = contact_id
    if job_id:
        filters["job_id"] = job_id

    result = client.list_records(
        "activities", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields, filters=filters,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="activities", columns=col_list)


@activities.command("get")
@click.argument("record_id")
@click.option("--fields", type=str, default=None, help="Comma-separated fields to return")
@click.pass_context
def activities_get(ctx, record_id, fields):
    """Get a single activity by JNID."""
    client = get_client(ctx)
    result = client.get_record("activities", record_id, fields=fields)
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="activities")


@activities.command("count")
@click.option("--query", "-q", type=str, default=None, help="ElasticSearch query string")
@click.pass_context
def activities_count(ctx, query):
    """Count activities matching an optional query."""
    client = get_client(ctx)
    count = client.count_records("activities", query=query)
    if ctx.obj["json_mode"]:
        print(format_json({"resource": "activities", "count": count}))
    else:
        click.echo(f"Activities: {count}")


@activities.command("search")
@click.argument("query")
@common_list_options
@click.pass_context
def activities_search(ctx, query, size, offset, sort_field, sort_dir, fields, columns, **_):
    """Search activity notes using ElasticSearch query syntax.

    \b
    Examples:
      jn activities search "note:*inspection*"
      jn activities search "note:leak AND record_type_name:note"
      jn activities search "created_by_name:John"
    """
    client = get_client(ctx)
    result = client.list_records(
        "activities", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="activities", columns=col_list)


@activities.command("notes")
@click.option("--size", "-s", type=int, default=50, help="Records per page")
@click.option("--offset", "-o", type=int, default=0, help="Starting index")
@click.option("--contact-id", type=str, default=None, help="Filter by contact JNID")
@click.option("--job-id", type=str, default=None, help="Filter by job JNID")
@click.option("--search", type=str, default=None, help="Search within note text")
@click.pass_context
def activities_notes(ctx, size, offset, contact_id, job_id, search):
    """List only note-type activities (shortcut for --type=note).

    Optimized for note scraping — returns note and date_created fields.
    """
    client = get_client(ctx)
    filters = {"record_type_name": "note"}
    if contact_id:
        filters["primary_id"] = contact_id
    if job_id:
        filters["job_id"] = job_id

    query = f"note:*{search}*" if search else None

    result = client.list_records(
        "activities", size=size, offset=offset,
        sort_field="date_created", sort_direction="desc",
        query=query, fields="note,date_created,jnid,created_by_name",
        filters=filters,
    )
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="activities")


# ── Invoices ────────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def invoices(ctx):
    """Read invoices (billing, payments, line items)."""
    pass


@invoices.command("list")
@common_list_options
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--contact-id", type=str, default=None, help="Filter by contact JNID")
@click.option("--job-id", type=str, default=None, help="Filter by job JNID")
@click.option("--date-from", type=str, default=None, help="Filter from date (Unix timestamp)")
@click.option("--date-to", type=str, default=None, help="Filter to date (Unix timestamp)")
@click.pass_context
def invoices_list(ctx, size, offset, sort_field, sort_dir, query, fields, columns,
                  status, contact_id, job_id, date_from, date_to):
    """List invoices with optional filtering and pagination."""
    client = get_client(ctx)
    filters = {}
    if status:
        filters["status"] = status
    if contact_id:
        filters["primary_id"] = contact_id
    if job_id:
        filters["job_id"] = job_id
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    result = client.list_records(
        "invoices", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields, filters=filters,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="invoices", columns=col_list)


@invoices.command("get")
@click.argument("record_id")
@click.option("--fields", type=str, default=None, help="Comma-separated fields to return")
@click.pass_context
def invoices_get(ctx, record_id, fields):
    """Get a single invoice by JNID (includes line items)."""
    client = get_client(ctx)
    result = client.get_record("invoices", record_id, fields=fields)
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="invoices")


@invoices.command("count")
@click.option("--query", "-q", type=str, default=None, help="ElasticSearch query string")
@click.pass_context
def invoices_count(ctx, query):
    """Count invoices matching an optional query."""
    client = get_client(ctx)
    count = client.count_records("invoices", query=query)
    if ctx.obj["json_mode"]:
        print(format_json({"resource": "invoices", "count": count}))
    else:
        click.echo(f"Invoices: {count}")


@invoices.command("search")
@click.argument("query")
@common_list_options
@click.pass_context
def invoices_search(ctx, query, size, offset, sort_field, sort_dir, fields, columns, **_):
    """Search invoices using ElasticSearch query syntax.

    \b
    Examples:
      jn invoices search "status:Paid"
      jn invoices search "status:Unpaid AND total:[1000 TO *]"
    """
    client = get_client(ctx)
    result = client.list_records(
        "invoices", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="invoices", columns=col_list)


# ── Estimates ───────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def estimates(ctx):
    """Read estimates (quotes, proposals)."""
    pass


@estimates.command("list")
@common_list_options
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--contact-id", type=str, default=None, help="Filter by contact JNID")
@click.option("--job-id", type=str, default=None, help="Filter by job JNID")
@click.pass_context
def estimates_list(ctx, size, offset, sort_field, sort_dir, query, fields, columns,
                   status, contact_id, job_id):
    """List estimates with optional filtering and pagination."""
    client = get_client(ctx)
    filters = {}
    if status:
        filters["status"] = status
    if contact_id:
        filters["primary_id"] = contact_id
    if job_id:
        filters["job_id"] = job_id

    result = client.list_records(
        "estimates", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields, filters=filters,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="estimates", columns=col_list)


@estimates.command("get")
@click.argument("record_id")
@click.option("--fields", type=str, default=None, help="Comma-separated fields to return")
@click.pass_context
def estimates_get(ctx, record_id, fields):
    """Get a single estimate by JNID (includes line items)."""
    client = get_client(ctx)
    result = client.get_record("estimates", record_id, fields=fields)
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="estimates")


@estimates.command("count")
@click.option("--query", "-q", type=str, default=None, help="ElasticSearch query string")
@click.pass_context
def estimates_count(ctx, query):
    """Count estimates matching an optional query."""
    client = get_client(ctx)
    count = client.count_records("estimates", query=query)
    if ctx.obj["json_mode"]:
        print(format_json({"resource": "estimates", "count": count}))
    else:
        click.echo(f"Estimates: {count}")


@estimates.command("search")
@click.argument("query")
@common_list_options
@click.pass_context
def estimates_search(ctx, query, size, offset, sort_field, sort_dir, fields, columns, **_):
    """Search estimates using ElasticSearch query syntax.

    \b
    Examples:
      jn estimates search "status:Approved"
      jn estimates search "total:[5000 TO *]"
    """
    client = get_client(ctx)
    result = client.list_records(
        "estimates", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="estimates", columns=col_list)


# ── Products ────────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def products(ctx):
    """Read products (materials, labor, catalog items)."""
    pass


@products.command("list")
@common_list_options
@click.option("--category", type=str, default=None, help="Filter by category")
@click.option("--status", type=str, default=None, help="Filter by status (active/inactive)")
@click.pass_context
def products_list(ctx, size, offset, sort_field, sort_dir, query, fields, columns,
                  category, status):
    """List products from the catalog."""
    client = get_client(ctx)
    filters = {}
    if category:
        filters["category"] = category
    if status:
        filters["status"] = status

    result = client.list_records(
        "products", size=size, offset=offset,
        sort_field=sort_field, sort_direction=sort_dir,
        query=query, fields=fields, filters=filters,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="products", columns=col_list)


@products.command("get")
@click.argument("record_id")
@click.option("--fields", type=str, default=None, help="Comma-separated fields to return")
@click.pass_context
def products_get(ctx, record_id, fields):
    """Get a single product by ID (includes UOMs and pricing)."""
    client = get_client(ctx)
    result = client.get_record("products", record_id, fields=fields)
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="products")


@products.command("search")
@click.argument("query")
@common_list_options
@click.pass_context
def products_search(ctx, query, size, offset, sort_field, sort_dir, fields, columns, **_):
    """Search products using ElasticSearch query syntax.

    \b
    Examples:
      jn products search "name:*shingle*"
      jn products search "item_type:labor"
    """
    client = get_client(ctx)
    result = client.list_records(
        "products", size=size, offset=offset,
        sort_field=sort_field, sort_direction=sort_dir,
        query=query, fields=fields,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="products", columns=col_list)


# ── Files ───────────────────────────────────────────────────────────────────

@cli.group()
@click.pass_context
def files(ctx):
    """Read files (documents, photos, attachments)."""
    pass


@files.command("list")
@common_list_options
@click.option("--contact-id", type=str, default=None, help="Filter by contact JNID")
@click.option("--job-id", type=str, default=None, help="Filter by job JNID")
@click.pass_context
def files_list(ctx, size, offset, sort_field, sort_dir, query, fields, columns,
               contact_id, job_id):
    """List files/documents with optional filtering."""
    client = get_client(ctx)
    filters = {}
    if contact_id:
        filters["primary_id"] = contact_id
    if job_id:
        filters["job_id"] = job_id

    result = client.list_records(
        "files", size=size, offset=offset,
        sort_field=sort_field or "date_updated",
        sort_direction=sort_dir or "desc",
        query=query, fields=fields, filters=filters,
    )
    col_list = columns.split(",") if columns else None
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="files", columns=col_list)


@files.command("get")
@click.argument("record_id")
@click.option("--fields", type=str, default=None, help="Comma-separated fields to return")
@click.pass_context
def files_get(ctx, record_id, fields):
    """Get file metadata by JNID."""
    client = get_client(ctx)
    result = client.get_record("files", record_id, fields=fields)
    output_results(result, json_mode=ctx.obj["json_mode"], resource_type="files")


@files.command("count")
@click.option("--query", "-q", type=str, default=None, help="ElasticSearch query string")
@click.pass_context
def files_count(ctx, query):
    """Count files matching an optional query."""
    client = get_client(ctx)
    count = client.count_records("files", query=query)
    if ctx.obj["json_mode"]:
        print(format_json({"resource": "files", "count": count}))
    else:
        click.echo(f"Files: {count}")


# ── Workflows ───────────────────────────────────────────────────────────────

@cli.command("workflows")
@click.pass_context
def workflows_cmd(ctx):
    """Show all workflow definitions and pipeline statuses.

    Returns the full account settings including workflow names,
    status stages, and their configurations.
    """
    client = get_client(ctx)
    result = client.get_account_settings()
    if ctx.obj["json_mode"]:
        print(format_json(result))
    else:
        if isinstance(result, dict):
            workflows = result.get("workflows", result)
            if isinstance(workflows, list):
                for wf in workflows:
                    name = wf.get("name", "Unnamed")
                    click.echo(f"\nWorkflow: {name}")
                    click.echo("-" * (len(name) + 10))
                    statuses = wf.get("statuses", [])
                    for s in statuses:
                        sname = s.get("name", "?")
                        click.echo(f"  - {sname}")
            else:
                print(format_json(result))
        else:
            print(format_json(result))


# ── Cross-cutting: find ─────────────────────────────────────────────────────

@cli.command("find")
@click.argument("record_id")
@click.pass_context
def find_cmd(ctx, record_id):
    """Find any record by JNID, auto-detecting its resource type.

    Searches contacts, jobs, tasks, activities, invoices, estimates,
    products, and files until the record is found.
    """
    client = get_client(ctx)
    resource_type, record = client.find_record(record_id)
    if resource_type is None:
        click.echo(f"Record '{record_id}' not found in any resource.", err=True)
        sys.exit(1)

    if ctx.obj["json_mode"]:
        print(format_json({"resource_type": resource_type, "record": record}))
    else:
        click.echo(f"Found in: {resource_type}")
        click.echo()
        output_results(record, json_mode=False, resource_type=resource_type)


# ── Cross-cutting: related ──────────────────────────────────────────────────

@cli.command("related")
@click.argument("record_id")
@click.option("--type", "resource_type", type=click.Choice(["contact", "job"]),
              default=None, help="Specify type (auto-detected if omitted)")
@click.pass_context
def related_cmd(ctx, record_id, resource_type):
    """Pull all records related to a contact or job.

    Given a JNID, fetches all associated jobs, tasks, activities,
    invoices, and estimates in one operation.
    """
    client = get_client(ctx)
    related = client.get_related(record_id, resource_type=resource_type)

    if ctx.obj["json_mode"]:
        print(format_json(related))
    else:
        for rtype, data in related.items():
            count = data.get("count", len(data.get("results", [])))
            records = data.get("results", [])
            click.echo(f"\n{rtype.upper()} ({count})")
            click.echo("=" * 40)
            if records:
                for r in records[:10]:  # Show first 10 per type
                    jnid = r.get("jnid", r.get("id", "?"))
                    name = (r.get("name") or r.get("title") or
                            r.get("number") or r.get("note", "")[:60] or jnid)
                    click.echo(f"  {jnid}: {name}")
                if count > 10:
                    click.echo(f"  ... and {count - 10} more")
            else:
                click.echo("  (none)")


# ── Cross-cutting: export ───────────────────────────────────────────────────

@cli.command("export")
@click.argument("resource", type=click.Choice([
    "contacts", "jobs", "tasks", "activities",
    "invoices", "estimates", "products", "files",
]))
@click.option("--max", "max_records", type=int, default=None,
              help="Max records to export (default: all)")
@click.option("--fields", type=str, default=None,
              help="Comma-separated fields to include")
@click.option("--query", "-q", type=str, default=None,
              help="ElasticSearch query to filter")
@click.option("--sort-field", type=str, default="date_updated",
              help="Field to sort by")
@click.option("--sort-dir", type=click.Choice(["asc", "desc"]), default="desc",
              help="Sort direction")
@click.pass_context
def export_cmd(ctx, resource, max_records, fields, query, sort_field, sort_dir):
    """Export all records of a type as JSONL (one JSON object per line).

    Automatically paginates through all records. Output is JSONL format
    for efficient streaming and line-by-line processing.

    \b
    Examples:
      jn export contacts > contacts.jsonl
      jn export activities --query="record_type_name:note" --fields=note,jnid
      jn export jobs --max=500 --sort-field=date_created
    """
    client = get_client(ctx)
    count = 0
    for record in client.paginate_all(
        resource,
        page_size=200,
        sort_field=sort_field,
        sort_direction=sort_dir,
        query=query,
        fields=fields,
        max_records=max_records,
    ):
        print(json.dumps(record, default=str, ensure_ascii=False))
        count += 1

    click.echo(f"\nExported {count} {resource}.", err=True)


# ── Account / Summary ───────────────────────────────────────────────────────

@cli.command("summary")
@click.pass_context
def summary(ctx):
    """Show account overview with record counts for ALL resources."""
    client = get_client(ctx)
    all_resources = list(JobNimbusClient.VALID_RESOURCES) + ["products"]
    counts = {}
    for resource in all_resources:
        try:
            counts[resource] = client.count_records(resource)
        except JobNimbusClientError:
            counts[resource] = "n/a"

    if ctx.obj["json_mode"]:
        print(format_json(counts))
    else:
        click.echo("Account Summary")
        click.echo("=" * 30)
        for resource, count in counts.items():
            click.echo(f"  {resource.capitalize():15s} {count}")


# ── REPL ────────────────────────────────────────────────────────────────────

class JobNimbusREPL(cmd.Cmd):
    """Interactive REPL for JobNimbus CLI."""

    intro = (
        "JobNimbus Read-Only REPL\n"
        "Type 'help' for commands, 'quit' to exit.\n"
        "All commands are READ-ONLY — no data modification.\n"
    )
    prompt = "jn> "

    def __init__(self, api_key=None, json_mode=False):
        super().__init__()
        self.api_key = api_key
        self.json_mode = json_mode
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = JobNimbusClient(api_key=self.api_key)
        return self._client

    def _run_cli(self, args_str):
        """Run a CLI command within the REPL."""
        args = args_str.split()
        try:
            ctx = cli.make_context("jn", args, parent=None)
            ctx.obj = {"api_key": self.api_key, "json_mode": self.json_mode}
            with ctx:
                cli.invoke(ctx)
        except SystemExit:
            pass
        except click.UsageError as e:
            click.echo(f"Usage error: {e}")
        except JobNimbusClientError as e:
            click.echo(f"API error: {e}")

    def do_contacts(self, line):
        """contacts [list|get|count|search] [options]"""
        self._run_cli(f"contacts {line}")

    def do_jobs(self, line):
        """jobs [list|get|count|search] [options]"""
        self._run_cli(f"jobs {line}")

    def do_tasks(self, line):
        """tasks [list|get|count|search] [options]"""
        self._run_cli(f"tasks {line}")

    def do_activities(self, line):
        """activities [list|get|count|search|notes] [options]"""
        self._run_cli(f"activities {line}")

    def do_invoices(self, line):
        """invoices [list|get|count|search] [options]"""
        self._run_cli(f"invoices {line}")

    def do_estimates(self, line):
        """estimates [list|get|count|search] [options]"""
        self._run_cli(f"estimates {line}")

    def do_products(self, line):
        """products [list|get|search] [options]"""
        self._run_cli(f"products {line}")

    def do_files(self, line):
        """files [list|get|count] [options]"""
        self._run_cli(f"files {line}")

    def do_workflows(self, line):
        """Show all workflow definitions and pipeline statuses."""
        self._run_cli("workflows")

    def do_find(self, line):
        """find <JNID> — auto-detect resource type"""
        self._run_cli(f"find {line}")

    def do_related(self, line):
        """related <JNID> [--type contact|job] — pull all related records"""
        self._run_cli(f"related {line}")

    def do_export(self, line):
        """export <resource> [options] — export all records as JSONL"""
        self._run_cli(f"export {line}")

    def do_summary(self, line):
        """Show account summary with record counts."""
        self._run_cli("summary")

    def do_json(self, line):
        """Toggle JSON output mode."""
        self.json_mode = not self.json_mode
        click.echo(f"JSON mode: {'ON' if self.json_mode else 'OFF'}")

    def do_quit(self, line):
        """Exit the REPL."""
        return True

    def do_exit(self, line):
        """Exit the REPL."""
        return True

    do_EOF = do_quit


@cli.command("repl")
@click.pass_context
def repl_cmd(ctx):
    """Start interactive REPL session."""
    try:
        r = JobNimbusREPL(api_key=ctx.obj.get("api_key"), json_mode=ctx.obj["json_mode"])
        r.cmdloop()
    except KeyboardInterrupt:
        click.echo("\nExiting REPL.")


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
