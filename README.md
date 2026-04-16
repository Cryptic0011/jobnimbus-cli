# JobNimbus Read CLI

A **read-only**, agent-native CLI for auditing everything in a JobNimbus CRM account. Built for AI agents to query contacts, jobs, tasks, activities, invoices, estimates, products, files, and workflows — with zero risk of data modification.

## Why

JobNimbus has no built-in reporting CLI. This tool lets AI agents (or humans) query the full JobNimbus API from the terminal with structured JSON output, ElasticSearch queries, pagination, and bulk export — all strictly read-only.

## Install

```bash
git clone https://github.com/gaborpatterson/jobnimbus-read-cli.git
cd jobnimbus-read-cli/agent-harness
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure

```bash
export JOBNIMBUS_API_KEY="your-api-key"
```

Get your API key from JobNimbus: **Settings > API Keys**.

## Quick Start

```bash
# Activate the venv
source agent-harness/.venv/bin/activate

# Account overview
jn summary

# List recent contacts
jn contacts list --size=10

# Search jobs
jn jobs search "status_name:Completed"

# Find unpaid invoices
jn --json invoices search "status:Unpaid"

# Pull everything for a contact
jn --json related CONTACT_JNID

# Export all notes as JSONL
jn export activities --query="record_type_name:note" > notes.jsonl
```

## Commands

| Command | Description |
|---------|-------------|
| `jn contacts` | Customers, leads, companies |
| `jn jobs` | Projects, work orders |
| `jn tasks` | To-dos, assignments |
| `jn activities` | Notes, emails, calls, audit trail |
| `jn invoices` | Billing, line items, payment status |
| `jn estimates` | Quotes, proposals |
| `jn products` | Material/labor catalog, pricing |
| `jn files` | Documents, photos, attachments |
| `jn workflows` | Pipeline stages and statuses |
| `jn find <JNID>` | Auto-detect resource type |
| `jn related <JNID>` | All records for a contact/job |
| `jn export <resource>` | Bulk JSONL with auto-pagination |
| `jn summary` | Record counts for all resources |
| `jn repl` | Interactive session |

Each resource command supports: `list`, `get`, `count`, `search`.

## Common Options

```
--json              Output raw JSON (for agents)
--size N            Records per page (max 1000)
--offset N          Pagination offset
--sort-field F      Sort by field (default: date_updated)
--sort-dir asc|desc Sort direction (default: desc)
--query Q           ElasticSearch/Lucene query
--fields F          Comma-separated fields (saves tokens)
--columns F         Custom table columns
```

## Query Syntax

The `--query` parameter supports ElasticSearch/Lucene syntax:

```bash
# Field match
jn contacts search "status_name:Lead"

# Wildcards
jn jobs search "name:*Smith*"

# Boolean
jn contacts search "city:Miami AND state_text:FL"

# Range
jn invoices search "total:[1000 TO *]"

# Combined
jn activities search "note:*leak* AND record_type_name:note"
```

## Agent Usage

For AI agent integration, add the skill to Claude Code:

```bash
# Copy skill definition
mkdir -p ~/.claude/skills/jobnimbus-cli
cp agent-harness/cli_anything/jobnimbus/skills/SKILL.md ~/.claude/skills/jobnimbus-cli/SKILL.md
```

Then set the API key in Claude Code settings (`~/.claude/settings.json`):

```json
{
  "env": {
    "JOBNIMBUS_API_KEY": "your-key"
  }
}
```

The agent will automatically use the CLI when you mention JobNimbus in conversation.

## Read-Only Guarantee

This CLI **only implements HTTP GET requests**. The API client class:
- Exposes no `create`, `update`, or `delete` methods
- The `_request()` method only calls `session.get()`
- Verified by automated tests that inspect the source code

## Tests

```bash
# Unit tests (no API key needed)
pytest cli_anything/jobnimbus/tests/test_core.py -v

# E2E tests (requires API key)
export JOBNIMBUS_API_KEY="your-key"
pytest cli_anything/jobnimbus/tests/test_full_e2e.py -v
```

## License

Private — internal use only.
