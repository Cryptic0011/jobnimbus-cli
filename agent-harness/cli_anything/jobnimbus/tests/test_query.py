"""Unit tests for the query -> JobNimbus filter translation."""

import pytest

from cli_anything.jobnimbus.core.query import (
    QueryError, build_filter, merge_filters, parse_query,
)


class TestParseQuery:
    def test_single_term(self):
        assert parse_query("status_name:Lead") == {"must": [{"term": {"status_name": "Lead"}}]}

    def test_and(self):
        assert parse_query("city:Miami AND state_text:FL") == {
            "must": [{"term": {"city": "Miami"}}, {"term": {"state_text": "FL"}}]
        }

    def test_or(self):
        assert parse_query("city:Orlando OR city:Tampa") == {
            "should": [{"term": {"city": "Orlando"}}, {"term": {"city": "Tampa"}}]
        }

    def test_not_and_dash(self):
        expected = {"must": [{"term": {"city": "Orlando"}}],
                    "must_not": [{"term": {"status_name": "Lead"}}]}
        assert parse_query("city:Orlando AND NOT status_name:Lead") == expected
        assert parse_query("city:Orlando AND -status_name:Lead") == expected

    def test_quoted_multi_word_value(self):
        assert parse_query('status_name:"Appointment Booked" AND city:Orlando') == {
            "must": [{"term": {"status_name": "Appointment Booked"}}, {"term": {"city": "Orlando"}}]
        }

    def test_quoted_value_may_contain_and(self):
        assert parse_query('name:"Smith AND Sons"') == {"must": [{"term": {"name": "Smith AND Sons"}}]}

    def test_wildcard(self):
        assert parse_query("name:*Smith*") == {"must": [{"wildcard": {"name": "*Smith*"}}]}

    def test_ranges(self):
        assert parse_query("total:[1000 TO *]") == {"must": [{"range": {"total": {"gte": 1000}}}]}
        assert parse_query("date_created:[1700000000 TO 1800000000]") == {
            "must": [{"range": {"date_created": {"gte": 1700000000, "lte": 1800000000}}}]
        }
        assert parse_query("total:[* TO 99.5]") == {"must": [{"range": {"total": {"lte": 99.5}}}]}

    def test_dotted_field(self):
        assert parse_query("related.id:abc") == {"must": [{"term": {"related.id": "abc"}}]}

    @pytest.mark.parametrize("bad", [
        "just some words",
        "status_name:Appointment Booked",       # unquoted multi-word value
        "city:Orlando AND (a:b OR c:d)",        # parentheses
        "a:b AND c:d OR e:f",                   # mixed AND / OR
        "total:[1000 UNTIL 5]",                 # bad range
        "",
    ])
    def test_unsupported_syntax_is_an_error_not_silently_ignored(self, bad):
        with pytest.raises(QueryError):
            parse_query(bad)


class TestBuildFilter:
    def test_nothing_requested(self):
        assert build_filter() is None
        assert build_filter(terms=[("status_name", None)]) is None

    def test_combines_query_raw_and_terms(self):
        result = build_filter(
            query="city:Orlando",
            raw='{"must": [{"exists": {"field": "email"}}], "must_not": [{"term": {"is_archived": true}}]}',
            terms=[("status_name", "Lead"), ("related.id", "c1"), ("related.id", "j1"), ("x", None)],
        )
        assert result == {
            "must": [
                {"exists": {"field": "email"}},
                {"term": {"city": "Orlando"}},
                {"term": {"status_name": "Lead"}},
                {"term": {"related.id": "c1"}},
                {"term": {"related.id": "j1"}},
            ],
            "must_not": [{"term": {"is_archived": True}}],
        }

    def test_bad_raw_filter(self):
        with pytest.raises(QueryError, match="not valid JSON"):
            build_filter(raw="{nope")
        with pytest.raises(QueryError, match="JSON object"):
            build_filter(raw="[1]")

    def test_merge_does_not_mutate_inputs(self):
        a = {"must": [{"term": {"a": 1}}]}
        merged = merge_filters(a, {"must": [{"term": {"b": 2}}]}, None)
        assert len(merged["must"]) == 2
        assert a == {"must": [{"term": {"a": 1}}]}
