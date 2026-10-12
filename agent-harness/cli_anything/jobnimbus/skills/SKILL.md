---
name: jobnimbus-read-cli
description: Read and write CLI for a JobNimbus CRM account — query, create, update and soft-delete contacts, jobs, tasks, invoices, estimates, products and orders; add notes; upload and download files; read payments, activities and workflows
version: 0.3.0
command: jn
aliases: [cli-anything-jobnimbus]
env:
  JOBNIMBUS_API_KEY: required
  JOBNIMBUS_READ_ONLY: optional (1 blocks every write)
  JOBNIMBUS_ACTOR: optional (email of the JobNimbus user to act as)
read_only: false
---

# JobNimbus CLI (`jn`)

Agent-native CLI for a JobNimbus account. Reads everything; writes contacts, jobs,
tasks, activities (notes), invoices, estimates, products, material orders, work
orders and files. Run `jn` directly — do not activate a venv.

## Before you write

Writes change the live CRM that the business runs on.

- Only make a change the user asked for. If they did not ask for that specific
  change, show them `jn --dry-run ...` output and get a yes first.
- `--dry-run` prints the exact request (method, URL, body) and sends nothing.
- `--read-only` or `JOBNIMBUS_READ_ONLY=1` blocks every write. If a write is
  refused as read-only, that is deliberate: tell the user, do not work around it.
- `update` is partial: only the fields you send change.
- `delete` is a soft delete (`is_active=false`) and needs `--yes`.
  Undo: `jn <resource> update <JNID> --set is_active:=true`.
- Read the record back after a write (`jn <resource> get <JNID>`) before reporting it done.

## Global options (before the command)

| Option | Effect |
|--------|--------|
| `--json` | Raw JSON output. Use this for anything you parse. |
| `--dry-run` | Preview a write without sending it |
| `--read-only` | Block all writes |
| `--actor EMAIL` | Act as that JobNimbus user (sets Created By) |
| `--api-key KEY` | Override `JOBNIMBUS_API_KEY` |

## Resources

| Resource | Read | Write |
|----------|------|-------|
| `contacts`, `jobs`, `tasks` | list get count search | create update delete |
| `invoices`, `estimates`, `products`, `materialorders`, `workorders` | list get count search | create update delete |
| `activities` | list get count search notes | create, add-note, update |
| `files` | list get count search download | upload, update |
| `payments`, `creditmemos` | list get count search | — (create payments with `jn api`) |

## Reading

```bash
jn --json <resource> list [--size N] [--offset N] [--sort-field F] [--sort-dir asc|desc]
                          [--fields a,b,c] [-q QUERY] [--filter JSON] [filter options]
jn --json <resource> search "QUERY" [same options]
jn --json <resource> count [-q QUERY] [filter options]
jn --json <resource> get <JNID> [--fields a,b,c]
```

List responses are always `{"results": [...], "count": N}`. `count` is the total
matching, not the page size. Default sort is `date_updated` descending.
Always pass `--fields` to keep output small.

### Filter options

| Resource | Options |
|----------|---------|
| contacts | `--status` `--type` |
| jobs | `--status` `--type` `--contact-id` |
| tasks | `--type` `--assignee USER_ID` `--contact-id` `--job-id` |
| activities | `--type` `--contact-id` `--job-id` |
| invoices, estimates, materialorders, workorders | `--status` `--contact-id` `--job-id` |
| files, payments, creditmemos | `--contact-id` `--job-id` |

`--status` matches `status_name`, `--type` matches `record_type_name`. Matching is
case-insensitive and exact (whole value).

### Query syntax (`-q` / `search`)

```bash
jn contacts search 'status_name:Lead'
jn contacts search 'status_name:"Appointment Booked" AND city:Orlando'   # quote multi-word values
jn contacts search 'city:Orlando OR city:Tampa'
jn contacts search 'city:Orlando AND NOT status_name:Lead'
jn jobs search 'name:*Smith*'                                            # wildcard
jn invoices search 'total:[1000 TO *]'                                   # range, * = open end
jn contacts search 'date_created:[1790000000 TO 1791000000]'             # Unix seconds
jn jobs search 'related.id:CONTACT_JNID'                                 # dotted fields work
```

AND and OR cannot be mixed and there are no parentheses; an unsupported query is an
error, never silently ignored. For anything richer pass the API's native filter:

```bash
jn contacts list --filter '{"must":[{"exists":{"field":"email"}}],"must_not":[{"term":{"status_name":"Lost"}}]}'
```

Filter clauses: `term`, `terms`, `wildcard`, `prefix`, `range`, `exists`, inside
`must` / `should` / `must_not`. Text fields such as `note` are matched whole, so
finding a word inside a note needs `note:*word*`, which is slow across all
activities — narrow it with `--job-id` / `--contact-id` or a date range.

### Cross-cutting reads

```bash
jn --json summary                      # record counts for every resource
jn --json find <JNID>                  # which resource is this id?
jn --json related <JNID>               # jobs, tasks, activities, invoices, estimates, files linked to a contact/job
jn --json workflows                    # account settings: workflows + statuses, custom fields, task/activity/file types, sources
jn activities notes --job-id <JNID> [--search TEXT]
jn files download <FILE_JNID> [-o PATH]
jn export <resource> [-q QUERY] [--fields a,b] [--max N] > out.jsonl     # JSONL, pages through everything
jn api GET account/users               # team members (ids for owners / sales_rep / --assignee)
jn api GET utility/uoms
```

`list --offset` stops at 9,999 (API limit). Use `export` for more, or narrow the query.

## Writing

Body input, on `create`, `update` and `api`:

- `--set KEY=VALUE` (repeatable) — value is a string. `KEY:=VALUE` is raw JSON
  (`is_active:=true`, `date_start:=1791900000`, `owners:='[{"id":"abc"}]'`).
  Dotted keys nest: `--set primary.id=abc`.
- `--data '{...}'`, `--data @body.json`, or `--data -` (stdin). `--set` is applied on top.

```bash
# Contact — needs a name (first/last, display_name or company), record_type_name and status_name
jn contacts create --set first_name=Sam --set last_name=Kent \
   --set record_type_name=Customer --set status_name=Lead
jn contacts update <JNID> --set status_name="Appointment Booked" --set zip=32806

# Job — needs name, record_type_name, status_name; link the contact with primary.id
jn jobs create --set name="Kent Roof" --set record_type_name=Roof --set status_name=New \
   --set primary.id=<CONTACT_JNID>
jn jobs update <JNID> --set status_name=Completed

# Task — needs title, date_start (Unix seconds), record_type_name (a task type), related
jn tasks create --data '{"title":"Call back","date_start":1791900000,
   "record_type_name":"Task","related":[{"id":"<JNID>"}],"owners":[{"id":"<USER_ID>"}]}'
jn tasks update <JNID> --set is_completed:=true

# Note on a contact or job
jn activities add-note <JNID> "Left a voicemail, will retry Thursday"

# Invoice / estimate — needs type, status, is_active, related, items. Start from an existing one:
jn --json invoices get <JNID> > inv.json      # edit, then:
jn invoices update <JNID> --data @inv.json

# File upload (under 100MB). --type: 1=Document 2=Photo 3=Email Attachment 5=Invoice
jn files upload ./photo.jpg --related <JOB_JNID> --type 2 --description "Front elevation"

# Re-point a note or file to another record (in place; author, date and text are kept)
jn activities update <JNID> --data '{"primary":{"id":"<CONTACT>"},"related":[{"id":"<CONTACT>","type":"contact"}]}'
jn files update <FILE_JNID> --set 'related:=["<CONTACT_JNID>"]'      # files take bare ids; the first is primary

# Soft delete
jn contacts delete <JNID> --yes
```

`status_name` and `record_type_name` must be names that exist in the account:
look them up with `jn --json workflows` first. A status belongs to one workflow
(`record_type_name`).

### Anything without a dedicated command

```bash
jn api POST account/leadsource --set SourceName=Google
jn api POST account/workflow/<WORKFLOW_ID>/status --set name="On Hold"
jn api POST account/customfield --data @field.json
jn api POST https://app.jobnimbus.com/api2/v2/payments --data @payment.json
```

`PATH` is relative to `https://app.jobnimbus.com/api1/`. Only `jobnimbus.com`
hosts are accepted. The API has GET, POST and PUT only.

## Errors

Failures print one line to stderr (`Error: ...`) and exit non-zero: 1 for API,
auth, query and read-only errors, 2 for bad command usage. A timed-out write is
not retried — check whether it landed (`get` / `search`) before sending it again.

## Key facts

- Timestamps are Unix seconds.
- JNIDs are strings. `number` is the human-facing record number, not the id.
- `related` is a list of `{"id": ...}` links; `primary` is the main one.
- Invoices, estimates, products and orders use the v2 API internally.
