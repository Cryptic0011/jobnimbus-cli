---
name: jobnimbus-read-cli
description: Read-only CLI for auditing everything in a JobNimbus CRM account — contacts, jobs, tasks, activities, invoices, estimates, products, files, and workflows
version: 0.2.0
command: jn
aliases: [cli-anything-jobnimbus]
env:
  JOBNIMBUS_API_KEY: required
capabilities:
  - list_contacts
  - list_jobs
  - list_tasks
  - list_activities
  - list_invoices
  - list_estimates
  - list_products
  - list_files
  - get_workflows
  - search_notes
  - account_summary
  - find_by_jnid
  - get_related_records
  - export_jsonl
  - pagination
  - elasticsearch_queries
read_only: true
---

# JobNimbus Read-Only CLI

Agent-native CLI for auditing everything in a JobNimbus account. **Strictly read-only** — only GET operations, zero data modification.

## Setup

```bash
export JOBNIMBUS_API_KEY="your-key"
```

## Resource Commands

Every resource supports `list`, `get`, `count`, and `search` subcommands (where applicable).

### contacts
```bash
jn contacts list [--size N] [--offset N] [--sort-field F] [--sort-dir asc|desc] [--query Q] [--fields F] [--status S] [--type T]
jn contacts get <JNID> [--fields F]
jn contacts count [--query Q]
jn contacts search "<ES query>"
```

### jobs
```bash
jn jobs list [--size N] [--offset N] [--sort-field F] [--sort-dir asc|desc] [--query Q] [--fields F] [--status S] [--type T] [--contact-id JNID]
jn jobs get <JNID> [--fields F]
jn jobs count [--query Q]
jn jobs search "<ES query>"
```

### tasks
```bash
jn tasks list [--size N] [--offset N] [--sort-field F] [--sort-dir asc|desc] [--query Q] [--fields F] [--status S] [--assignee A] [--contact-id JNID] [--job-id JNID]
jn tasks get <JNID> [--fields F]
jn tasks count [--query Q]
jn tasks search "<ES query>"
```

### activities
```bash
jn activities list [--size N] [--offset N] [--sort-field F] [--sort-dir asc|desc] [--query Q] [--fields F] [--type T] [--contact-id JNID] [--job-id JNID]
jn activities get <JNID> [--fields F]
jn activities count [--query Q]
jn activities search "<ES query>"
jn activities notes [--size N] [--contact-id JNID] [--job-id JNID] [--search TEXT]
```

### invoices
```bash
jn invoices list [--size N] [--offset N] [--sort-field F] [--sort-dir asc|desc] [--query Q] [--fields F] [--status S] [--contact-id JNID] [--job-id JNID] [--date-from TS] [--date-to TS]
jn invoices get <JNID> [--fields F]
jn invoices count [--query Q]
jn invoices search "<ES query>"
```

### estimates
```bash
jn estimates list [--size N] [--offset N] [--sort-field F] [--sort-dir asc|desc] [--query Q] [--fields F] [--status S] [--contact-id JNID] [--job-id JNID]
jn estimates get <JNID> [--fields F]
jn estimates count [--query Q]
jn estimates search "<ES query>"
```

### products
```bash
jn products list [--size N] [--offset N] [--sort-field F] [--sort-dir asc|desc] [--query Q] [--fields F] [--category C] [--status S]
jn products get <ID> [--fields F]
jn products search "<ES query>"
```

### files
```bash
jn files list [--size N] [--offset N] [--sort-field F] [--sort-dir asc|desc] [--query Q] [--fields F] [--contact-id JNID] [--job-id JNID]
jn files get <JNID> [--fields F]
jn files count [--query Q]
```

### workflows
```bash
jn workflows
```

## Cross-Cutting Commands

### find — auto-detect resource type
```bash
jn find <JNID>
jn --json find <JNID>
```

### related — pull everything for a contact or job
```bash
jn related <JNID>
jn --json related <JNID>
jn --json related <JNID> --type contact
jn --json related <JNID> --type job
```

### export — bulk JSONL export with auto-pagination
```bash
jn export contacts > contacts.jsonl
jn export activities --query="record_type_name:note" --fields=note,jnid > notes.jsonl
jn export jobs --max=500 --sort-field=date_created
jn export invoices --query="status:Unpaid" > unpaid.jsonl
```

### summary — account overview
```bash
jn summary
jn --json summary
```

### repl — interactive session
```bash
jn repl
```

## Global Options

| Option | Description |
|--------|-------------|
| `--json` | Output raw JSON (for programmatic consumption) |
| `--api-key KEY` | Override env var API key |
| `--version` | Show version |
| `--help` | Show help |

## Agent-Optimized Workflows

### Full account audit
```bash
jn --json summary
```

### List all jobs updated in the last 24 hours
```bash
jn --json jobs list --sort-field=date_updated --sort-dir=desc --size=100
```

### Search activity notes for keywords
```bash
jn --json activities search "note:*leak*" --fields=note,date_created,jnid
```

### Get everything related to a contact
```bash
jn --json related CONTACT_JNID --type contact
```

### Find unpaid invoices
```bash
jn --json invoices search "status:Unpaid" --size=100
```

### Find large estimates
```bash
jn --json estimates search "total:[5000 TO *]" --size=50
```

### Export all notes as JSONL for analysis
```bash
jn export activities --query="record_type_name:note" --fields=note,date_created,jnid,created_by_name > all_notes.jsonl
```

### Get all pipeline stages
```bash
jn --json workflows
```

### Find product catalog items
```bash
jn --json products search "name:*shingle*"
jn --json products list --category=roofing
```

### List all files for a job
```bash
jn --json files list --job-id=JOB_JNID
```

### Token-efficient field selection
```bash
jn --json contacts list --fields=jnid,first_name,last_name,status_name --size=100
jn --json jobs list --fields=jnid,name,status_name,date_updated --size=100
jn --json invoices list --fields=jnid,number,status,total --size=100
```

### Boolean ElasticSearch queries
```bash
jn --json contacts search "city:Miami AND state_text:FL"
jn --json jobs search "status_name:Completed AND record_type_name:Roof"
jn --json activities search "note:*damage* AND record_type_name:note"
jn --json invoices search "status:Paid AND total:[1000 TO *]"
```

### Look up any record by JNID
```bash
jn --json find SOME_JNID
```

## Response Formats

### List response (--json)
```json
{"results": [...], "count": 1234}
```

### Count response (--json)
```json
{"resource": "contacts", "count": 1234}
```

### Summary response (--json)
```json
{"contacts": 500, "jobs": 200, "tasks": 150, "activities": 3000, "invoices": 75, "estimates": 40, "files": 800, "products": 120}
```

### Find response (--json)
```json
{"resource_type": "contacts", "record": {...}}
```

### Related response (--json)
```json
{"jobs": {"results": [...], "count": 5}, "tasks": {"results": [...], "count": 3}, "activities": {"results": [...], "count": 12}, "invoices": {"results": [...], "count": 2}, "estimates": {"results": [...], "count": 1}}
```

### Export format (JSONL)
```
{"jnid":"abc","name":"John",...}
{"jnid":"def","name":"Jane",...}
```

## Key Notes

- All timestamps are Unix epoch (seconds since 1970-01-01)
- JNIDs are string identifiers unique to each record
- `--size` max is 1000 per request; use `export` for bulk retrieval
- Default sort is `date_updated` descending
- ElasticSearch queries use Lucene syntax
- Products use a v2 API endpoint internally
- This CLI is **strictly read-only** — no POST/PUT/DELETE operations exist
