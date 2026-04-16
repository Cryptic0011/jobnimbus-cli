# JobNimbus CLI — Test Plan & Results

## Test Plan

### Unit Tests (`test_core.py`) — 61 tests

#### Client Init (5)
| Test | Verifies |
|------|----------|
| `test_requires_api_key` | Error when no key |
| `test_accepts_explicit_key` | Direct key works |
| `test_reads_env_var` | Env var works |
| `test_explicit_key_overrides_env` | Explicit priority |
| `test_auth_header_set` | Bearer token in headers |

#### Client Validation (4)
| Test | Verifies |
|------|----------|
| `test_rejects_invalid_resource` | ValueError for bad names |
| `test_accepts_valid_resources` | All 7 core resources recognized |
| `test_accepts_products_resource` | Products use v2 endpoint |
| `test_size_capped_at_max` | Size > 1000 clamped |

#### Client Requests (6)
| Test | Verifies |
|------|----------|
| `test_successful_get` | 200 parsed correctly |
| `test_auth_error_401` | 401 raises AuthError |
| `test_auth_error_403` | 403 raises AuthError |
| `test_rate_limit_retry` | 429 retries then succeeds |
| `test_rate_limit_exhausted` | 429 x3 raises RateLimitError |
| `test_server_error` | 500 raises ClientError |

#### Pagination (4)
| Test | Verifies |
|------|----------|
| `test_paginate_all_single_page` | Single page works |
| `test_paginate_all_multi_page` | Multi-page works |
| `test_paginate_all_max_records` | max_records respected |
| `test_paginate_all_empty` | Empty set handled |

#### Params (4)
| Test | Verifies |
|------|----------|
| `test_query_param_mapping` | ES query mapped correctly |
| `test_sort_params` | Sort field/direction passed |
| `test_fields_param` | Fields parameter works |
| `test_filters_passed` | Custom filters work |

#### Formatting (13)
Covers: unix_to_iso (4), format_table (5), format_record_summary (4), format_json (1)

#### Read-Only Guarantee (4)
| Test | Verifies |
|------|----------|
| `test_no_post_method` | No create/post methods exist |
| `test_no_put_method` | No update/put methods exist |
| `test_no_delete_method` | No delete methods exist |
| `test_only_get_in_request` | Source code only uses session.get |

#### New Resources (6)
| Test | Verifies |
|------|----------|
| `test_list_invoices` | Invoices endpoint works |
| `test_list_estimates` | Estimates endpoint works |
| `test_list_files` | Files endpoint works |
| `test_products_uses_v2_endpoint` | Products route to v2 |
| `test_get_product_uses_v2_endpoint` | Product GET routes to v2 |
| `test_get_account_settings` | Settings/workflows endpoint |

#### Find Record (3)
| Test | Verifies |
|------|----------|
| `test_find_in_contacts` | Auto-detection works |
| `test_find_not_found` | Returns None on miss |
| `test_find_checks_multiple_resources` | Searches across types |

#### Get Related (3)
| Test | Verifies |
|------|----------|
| `test_related_for_contact` | All related types returned |
| `test_related_for_job` | Job relationships correct |
| `test_related_handles_api_errors` | Graceful error handling |

#### Format New Resources (4)
| Test | Verifies |
|------|----------|
| `test_invoice_summary` | Invoice formatting |
| `test_estimate_summary` | Estimate formatting |
| `test_product_summary` | Product formatting |
| `test_file_summary` | File formatting |

#### CLI Subprocess (4)
| Test | Verifies |
|------|----------|
| `test_version` | --version works |
| `test_help` | All 14 commands in help output |
| `test_contacts_help` | Subcommand help works |
| `test_no_api_key_error` | Missing key → non-zero exit |

### E2E Tests (`test_full_e2e.py`) — 28 tests

Requires `JOBNIMBUS_API_KEY`. Tests cover: contacts (6), jobs (4), tasks (2), activities (3), invoices (2), estimates (2), products (1), files (1), workflows (1), summary (1), data integrity (5).

## Test Results

**Run Date:** 2026-04-16
**Python:** 3.14.4 | **pytest:** 9.0.3 | **Platform:** macOS (darwin)

### Unit Tests: 61/61 PASSED (0.40s)

All passing. 100% pass rate.

### E2E Tests: 28/28 SKIPPED (no JOBNIMBUS_API_KEY set)

To run E2E tests:
```bash
export JOBNIMBUS_API_KEY="your-key"
pytest cli_anything/jobnimbus/tests/test_full_e2e.py -v
```

### Summary
- **Unit tests:** 61 passed, 0 failed
- **E2E tests:** 28 skipped (require API key)
- **Total:** 89 collected, 61 passed, 28 skipped
- **Pass rate (unit):** 100%
