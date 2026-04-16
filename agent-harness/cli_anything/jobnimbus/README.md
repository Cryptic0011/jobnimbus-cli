# cli-anything-jobnimbus

Read-only agent-native CLI for auditing everything in a JobNimbus account.

## Installation

```bash
python3 -m pip install --user .
```

## Configuration

```bash
export JOBNIMBUS_API_KEY="your-api-key-here"
```

## Usage

### Resource Commands
```bash
# Contacts
jn contacts list --size=10
jn contacts search "status_name:Lead"
jn contacts get JNID123

# Jobs
jn jobs list --sort-field=date_updated
jn jobs search "status_name:Completed"

# Tasks
jn tasks list --status=Open

# Activities / Notes
jn activities list --size=20
jn activities notes --search="leak"
jn --json activities search "note:*inspection*"

# Invoices
jn invoices list --size=10
jn invoices search "status:Unpaid"

# Estimates
jn estimates list --size=10
jn estimates search "total:[5000 TO *]"

# Products
jn products list
jn products search "name:*shingle*"

# Files
jn files list --job-id=JNID456

# Workflows / Pipeline stages
jn workflows
```

### Cross-Cutting Commands
```bash
# Auto-detect resource type by JNID
jn find JNID123

# Pull all related records for a contact or job
jn related JNID123 --type contact

# Export all records as JSONL
jn export contacts > contacts.jsonl
jn export activities --query="record_type_name:note" > notes.jsonl

# Account overview
jn summary
```

### JSON Output (for agent consumption)
```bash
jn --json contacts list --size=5
jn --json summary
jn --json related JNID123
```

### Interactive REPL
```bash
jn repl
```

## Read-Only Guarantee

This CLI **only implements GET requests**. No data is ever created, modified, or deleted. This is enforced at the API client level — the client class exposes no write methods.

Command coverage notes:
- `products` supports `list`, `get`, and `search`
- `files` supports `list`, `get`, and `count`
