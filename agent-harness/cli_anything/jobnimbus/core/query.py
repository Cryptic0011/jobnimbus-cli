"""Translate CLI queries into the JobNimbus `filter` JSON parameter.

The API only accepts `?filter=<JSON>` with must / should / must_not lists of
term, wildcard, range, prefix and exists clauses. It rejects Lucene
query_string syntax, so `field:value AND ...` queries are translated here.
"""

import json
import re

_CLAUSE = re.compile(
    r'\s*(?P<neg>NOT\s+|-)?(?P<field>[\w.]+):(?P<value>"[^"]*"|\[[^\]]*\]|\S+)\s*'
)
_JOIN = re.compile(r"(AND|OR)\b")
_RANGE = re.compile(r"\[\s*(\S+)\s+TO\s+(\S+)\s*\]$")

SYNTAX_HELP = (
    'Supported: field:value, field:"two words", field:*wild*, field:[lo TO hi], '
    "NOT field:value, joined by AND or OR (not mixed, no parentheses). "
    "Use --filter with raw JSON for anything else."
)


class QueryError(ValueError):
    """Raised when a query cannot be translated into a filter."""


def _number(text):
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _clause(field, value):
    if value.startswith("["):
        match = _RANGE.match(value)
        if not match:
            raise QueryError(f"Bad range '{value}'. Use field:[lo TO hi], * for open ends.")
        bounds = zip(("gte", "lte"), match.groups())
        return {"range": {field: {op: _number(v) for op, v in bounds if v != "*"}}}
    if value.startswith('"'):
        return {"term": {field: value.strip('"')}}
    if "*" in value or "?" in value:
        return {"wildcard": {field: value}}
    return {"term": {field: value}}


def parse_query(query):
    """Translate 'a:b AND NOT c:[1 TO *]' into a JobNimbus filter dict."""
    pos, joins, positive, negative = 0, set(), [], []
    while True:
        match = _CLAUSE.match(query, pos)
        if not match:
            raise QueryError(f"Cannot parse query near '{query[pos:pos + 40]}'. {SYNTAX_HELP}")
        target = negative if match["neg"] else positive
        target.append(_clause(match["field"], match["value"]))
        pos = match.end()
        if pos >= len(query):
            break
        join = _JOIN.match(query, pos)
        if not join:
            raise QueryError(
                f"Expected AND/OR near '{query[pos:pos + 40]}' "
                f"(quote multi-word values). {SYNTAX_HELP}"
            )
        joins.add(join[1])
        pos = join.end()
    if len(joins) > 1:
        raise QueryError(f"Cannot mix AND and OR. {SYNTAX_HELP}")

    parsed = {}
    if positive:
        parsed["should" if joins == {"OR"} else "must"] = positive
    if negative:
        parsed["must_not"] = negative
    return parsed


def merge_filters(*filters):
    """Combine filter dicts by concatenating their clause lists. Returns a new dict."""
    merged = {}
    for flt in filters:
        for key, clauses in (flt or {}).items():
            merged[key] = merged.get(key, []) + list(clauses)
    return merged


def build_filter(query=None, raw=None, terms=None):
    """Build one filter dict from a query string, raw filter JSON and exact-match
    terms given as (field, value) pairs. Returns None when nothing was asked for.
    """
    parts = []
    if raw:
        try:
            parsed_raw = json.loads(raw)
        except json.JSONDecodeError as e:
            raise QueryError(f"--filter is not valid JSON: {e}")
        if not isinstance(parsed_raw, dict):
            raise QueryError('--filter must be a JSON object like {"must": [...]}')
        parts.append(parsed_raw)
    if query:
        parts.append(parse_query(query))
    if terms:
        parts.append({"must": [{"term": {k: v}} for k, v in terms if v is not None]})
    merged = {k: v for k, v in merge_filters(*parts).items() if v}
    return merged or None
