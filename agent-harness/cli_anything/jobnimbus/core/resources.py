"""Resource table: how each JobNimbus record type maps onto the API.

Verified against the live API and the public Postman docs:
- invoices / estimates / products / material orders / work orders live under v2/
  (the v1 single-record GET for invoices and estimates returns 404).
- activities and files return their rows under "activity" / "files", not "results".
- files, payments and credit memos have no JSON single-record GET.
- "Delete" is a soft delete everywhere: PUT {"is_active": false}.
- PUT on activities and files is undocumented but works (used to re-parent records
  on this account); a documented delete for them does not exist.
"""

from dataclasses import dataclass, field

CREATE, UPDATE, DELETE = "create", "update", "delete"
ALL_WRITES = (CREATE, UPDATE, DELETE)


@dataclass(frozen=True)
class Resource:
    path: str
    help: str
    list_key: str = "results"
    single_get: bool = True
    writes: tuple = ALL_WRITES
    # CLI option name -> API field it filters on
    filters: dict = field(default_factory=dict)


_RELATED = {"contact-id": "related.id", "job-id": "related.id"}

RESOURCES = {
    "contacts": Resource(
        "contacts", "Contacts (customers, leads, companies).",
        filters={"status": "status_name", "type": "record_type_name"},
    ),
    "jobs": Resource(
        "jobs", "Jobs (projects).",
        filters={"status": "status_name", "type": "record_type_name", "contact-id": "primary.id"},
    ),
    "tasks": Resource(
        "tasks", "Tasks (to-dos, appointments).",
        filters={"type": "record_type_name", "assignee": "owners.id", **_RELATED},
    ),
    "activities": Resource(
        "activities", "Activities (notes, emails, calls, audit trail).",
        list_key="activity", writes=(CREATE, UPDATE),
        filters={"type": "record_type_name", **_RELATED},
    ),
    "invoices": Resource(
        "v2/invoices", "Invoices (billing, line items).",
        filters={"status": "status_name", **_RELATED},
    ),
    "estimates": Resource(
        "v2/estimates", "Estimates (quotes, proposals).",
        filters={"status": "status_name", **_RELATED},
    ),
    "products": Resource("v2/products", "Products (material/labor catalog)."),
    "materialorders": Resource(
        "v2/materialorders", "Material orders.",
        filters={"status": "status_name", **_RELATED},
    ),
    "workorders": Resource(
        "v2/workorders", "Work orders.",
        filters={"status": "status_name", **_RELATED},
    ),
    "files": Resource(
        "files", "Files (documents, photos, attachments).",
        list_key="files", single_get=False, writes=(UPDATE,), filters=dict(_RELATED),
    ),
    "payments": Resource(
        "payments", "Payments (read-only here; create via `jn api`).",
        single_get=False, writes=(), filters=dict(_RELATED),
    ),
    "creditmemos": Resource(
        "creditmemos", "Credit memos (read-only).",
        single_get=False, writes=(), filters=dict(_RELATED),
    ),
}


def get_resource(name):
    try:
        return RESOURCES[name]
    except KeyError:
        raise ValueError(
            f"Invalid resource '{name}'. Must be one of: {', '.join(RESOURCES)}"
        ) from None
