"""Output formatting utilities for CLI display."""

import json
import sys
from datetime import datetime, timezone


def unix_to_iso(timestamp):
    """Convert Unix timestamp to ISO 8601 string."""
    if timestamp is None:
        return None
    try:
        ts = float(timestamp)
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return str(timestamp)


def format_json(data, indent=2):
    """Format data as pretty-printed JSON."""
    return json.dumps(data, indent=indent, default=str, ensure_ascii=False)


def format_table(records, columns=None, max_width=None):
    """Format records as an ASCII table.

    Args:
        records: List of dicts
        columns: List of column names to display (None = auto-detect)
        max_width: Max width per column (None = unlimited)
    """
    if not records:
        return "(no records)"

    if columns is None:
        columns = []
        seen = set()
        for r in records:
            for k in r.keys():
                if k not in seen:
                    columns.append(k)
                    seen.add(k)

    # Build rows
    rows = []
    for r in records:
        row = []
        for col in columns:
            val = r.get(col, "")
            if val is None:
                val = ""
            elif isinstance(val, (dict, list)):
                val = json.dumps(val, default=str)
            else:
                val = str(val)
            if max_width and len(val) > max_width:
                val = val[:max_width - 3] + "..."
            row.append(val)
        rows.append(row)

    # Calculate widths
    widths = [len(c) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    # Build output
    header = " | ".join(c.ljust(widths[i]) for i, c in enumerate(columns))
    separator = "-+-".join("-" * w for w in widths)
    lines = [header, separator]
    for row in rows:
        lines.append(" | ".join(val.ljust(widths[i]) for i, val in enumerate(row)))

    return "\n".join(lines)


def format_record_summary(record, resource_type):
    """Format a single record as a human-readable summary."""
    lines = []
    jnid = record.get("jnid", record.get("id", "unknown"))
    lines.append(f"  ID: {jnid}")

    if resource_type == "contacts":
        name_parts = [record.get("first_name", ""), record.get("last_name", "")]
        name = " ".join(p for p in name_parts if p).strip()
        if name:
            lines.append(f"  Name: {name}")
        if record.get("company_name"):
            lines.append(f"  Company: {record['company_name']}")
        if record.get("email"):
            lines.append(f"  Email: {record['email']}")
        if record.get("status_name"):
            lines.append(f"  Status: {record['status_name']}")

    elif resource_type == "jobs":
        if record.get("name"):
            lines.append(f"  Name: {record['name']}")
        if record.get("number"):
            lines.append(f"  Number: {record['number']}")
        if record.get("status_name"):
            lines.append(f"  Status: {record['status_name']}")
        if record.get("record_type_name"):
            lines.append(f"  Type: {record['record_type_name']}")

    elif resource_type == "tasks":
        if record.get("title"):
            lines.append(f"  Title: {record['title']}")
        if record.get("status"):
            lines.append(f"  Status: {record['status']}")
        if record.get("due_date"):
            lines.append(f"  Due: {unix_to_iso(record['due_date'])}")

    elif resource_type == "activities":
        if record.get("note"):
            note = record["note"]
            if len(note) > 200:
                note = note[:197] + "..."
            lines.append(f"  Note: {note}")
        if record.get("record_type_name"):
            lines.append(f"  Type: {record['record_type_name']}")

    elif resource_type == "invoices":
        if record.get("number"):
            lines.append(f"  Number: {record['number']}")
        if record.get("title"):
            lines.append(f"  Title: {record['title']}")
        if record.get("status"):
            lines.append(f"  Status: {record['status']}")
        if record.get("total") is not None:
            lines.append(f"  Total: ${record['total']:.2f}")
        if record.get("subtotal") is not None:
            lines.append(f"  Subtotal: ${record['subtotal']:.2f}")

    elif resource_type == "estimates":
        if record.get("number"):
            lines.append(f"  Number: {record['number']}")
        if record.get("title"):
            lines.append(f"  Title: {record['title']}")
        if record.get("status"):
            lines.append(f"  Status: {record['status']}")
        if record.get("total") is not None:
            lines.append(f"  Total: ${record['total']:.2f}")

    elif resource_type == "products":
        if record.get("name"):
            lines.append(f"  Name: {record['name']}")
        if record.get("sku"):
            lines.append(f"  SKU: {record['sku']}")
        if record.get("item_type"):
            lines.append(f"  Type: {record['item_type']}")
        if record.get("is_active") is not None:
            lines.append(f"  Active: {record['is_active']}")

    elif resource_type == "files":
        if record.get("filename") or record.get("name"):
            lines.append(f"  Name: {record.get('filename') or record.get('name')}")
        if record.get("content_type"):
            lines.append(f"  Type: {record['content_type']}")
        if record.get("size"):
            lines.append(f"  Size: {record['size']}")

    if record.get("date_created"):
        lines.append(f"  Created: {unix_to_iso(record['date_created'])}")
    if record.get("date_updated"):
        lines.append(f"  Updated: {unix_to_iso(record['date_updated'])}")

    return "\n".join(lines)


def output_results(data, json_mode=False, resource_type=None, columns=None):
    """Primary output dispatcher.

    Args:
        data: API response dict or list of records
        json_mode: If True, output raw JSON
        resource_type: Type of resource for formatting hints
        columns: Column names for table output
    """
    if json_mode:
        print(format_json(data))
        return

    if isinstance(data, dict):
        records = data.get("results", [])
        count = data.get("count", len(records))
        print(f"Total: {count} | Showing: {len(records)}")
        print()
    elif isinstance(data, list):
        records = data
    else:
        print(format_json(data))
        return

    if not records:
        print("(no records found)")
        return

    if columns:
        print(format_table(records, columns=columns, max_width=60))
    else:
        for i, record in enumerate(records):
            if i > 0:
                print()
            print(format_record_summary(record, resource_type or ""))
