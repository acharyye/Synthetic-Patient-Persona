"""The validator is the boundary between an LLM's output and the database, so
the interesting tests are the ones that try to get past it.
"""
import pytest

from spp.graphrag import UnsafeCypher, validate_cypher

GOOD = (
    "MATCH (d:Disease)-[:PRESENTS_SYMPTOM]->(s:Symptom) "
    "WHERE toLower(d.name) = toLower($condition) "
    "RETURN d.name AS source, 'PRESENTS_SYMPTOM' AS rel, s.name AS target LIMIT 10"
)


class TestAccepts:
    def test_a_well_formed_query_passes_unchanged(self):
        assert validate_cypher(GOOD) == GOOD

    def test_missing_limit_is_appended(self):
        query = (
            "MATCH (d:Disease) WHERE d.name = $condition "
            "RETURN d.name AS source, 'IS' AS rel, d.kind AS target"
        )
        assert validate_cypher(query, max_limit=25).endswith("LIMIT 25")

    def test_trailing_semicolon_is_tolerated(self):
        assert validate_cypher(GOOD + ";") == GOOD

    def test_optional_match_and_alternation_are_allowed(self):
        query = (
            "OPTIONAL MATCH (c:Compound)-[:TREATS|PALLIATES]->(d:Disease) "
            "WHERE toLower(d.name) = toLower($condition) "
            "RETURN c.name AS source, 'TREATS' AS rel, d.name AS target LIMIT 5"
        )
        assert validate_cypher(query) == query

    def test_bounded_variable_length_is_allowed(self):
        query = (
            "MATCH (d:Disease)-[:ASSOCIATES_GENE*1..2]->(g:Gene) "
            "WHERE d.name = $condition "
            "RETURN d.name AS source, 'X' AS rel, g.name AS target LIMIT 5"
        )
        assert validate_cypher(query) == query


class TestRejectsWrites:
    @pytest.mark.parametrize(
        "query",
        [
            "MATCH (d:Disease) SET d.name = 'x' RETURN d.name AS source LIMIT 1",
            "MATCH (d:Disease) DETACH DELETE d RETURN 1 AS source LIMIT 1",
            "MATCH (d:Disease) MERGE (e:Disease {name:'x'}) RETURN 1 AS source LIMIT 1",
            "MATCH (d:Disease) REMOVE d:Disease RETURN 1 AS source LIMIT 1",
            "MATCH (d:Disease) CREATE (x:Disease) RETURN 1 AS source LIMIT 1",
            "MATCH (d:Disease) FOREACH (x IN [1] | SET d.n = 1) RETURN 1 AS s LIMIT 1",
        ],
    )
    def test_write_clauses_are_rejected(self, query):
        with pytest.raises(UnsafeCypher, match="forbidden clause"):
            validate_cypher(query)

    def test_procedure_calls_are_rejected(self):
        with pytest.raises(UnsafeCypher, match="forbidden clause"):
            validate_cypher(
                "MATCH (d:Disease) CALL apoc.cypher.run('MATCH (n) DETACH DELETE n', {}) "
                "YIELD value RETURN 1 AS source LIMIT 1"
            )

    def test_admin_and_io_clauses_are_rejected(self):
        for query in (
            "MATCH (d:Disease) LOAD CSV FROM 'http://x' AS r RETURN 1 AS source LIMIT 1",
            "MATCH (d:Disease) RETURN 1 AS source UNION MATCH (n:Gene) RETURN 1 AS source",
        ):
            with pytest.raises(UnsafeCypher, match="forbidden clause"):
                validate_cypher(query)


class TestRejectsEvasion:
    def test_second_statement_is_rejected(self):
        with pytest.raises(UnsafeCypher):
            validate_cypher(GOOD + "; MATCH (n:Gene) DETACH DELETE n")

    def test_a_write_hidden_in_a_comment_does_not_smuggle_a_second_statement(self):
        """Comments are stripped for scanning, so this is safe — but the ';'
        check must still fire on the raw text."""
        with pytest.raises(UnsafeCypher, match="multiple statements"):
            validate_cypher(GOOD + " // harmless\n; CREATE (x:Disease)")

    def test_keyword_inside_a_string_literal_is_not_a_false_positive(self):
        query = (
            "MATCH (d:Disease) WHERE d.name = 'CREATE DELETE SET' "
            "RETURN d.name AS source, 'x' AS rel, d.kind AS target LIMIT 5"
        )
        assert validate_cypher(query) == query

    def test_colon_inside_a_string_literal_is_not_read_as_a_label(self):
        query = (
            "MATCH (d:Disease) WHERE d.name = 'a:NotALabel' "
            "RETURN d.name AS source, 'x' AS rel, d.kind AS target LIMIT 5"
        )
        assert validate_cypher(query) == query

    def test_backticked_identifiers_are_rejected(self):
        with pytest.raises(UnsafeCypher, match="backtick"):
            validate_cypher(
                "MATCH (d:`Disease`) RETURN d.name AS source, 'x' AS rel, "
                "d.kind AS target LIMIT 5"
            )

    def test_case_does_not_evade_the_keyword_scan(self):
        with pytest.raises(UnsafeCypher, match="forbidden clause"):
            validate_cypher("MATCH (d:Disease) dEtAcH dElEtE d RETURN 1 AS source LIMIT 1")


class TestRejectsOutOfSchema:
    def test_unknown_label_is_rejected(self):
        with pytest.raises(UnsafeCypher, match="unknown label"):
            validate_cypher(
                "MATCH (u:User)-[:PRESENTS_SYMPTOM]->(s:Symptom) "
                "RETURN u.name AS source, 'x' AS rel, s.name AS target LIMIT 5"
            )

    def test_unknown_relationship_type_is_rejected(self):
        with pytest.raises(UnsafeCypher, match="unknown label or relationship"):
            validate_cypher(
                "MATCH (d:Disease)-[:SECRETLY_KNOWS]->(s:Symptom) "
                "RETURN d.name AS source, 'x' AS rel, s.name AS target LIMIT 5"
            )

    def test_unbound_parameter_is_rejected(self):
        with pytest.raises(UnsafeCypher, match="unbound parameter"):
            validate_cypher(
                "MATCH (d:Disease) WHERE d.name = $secret "
                "RETURN d.name AS source, 'x' AS rel, d.kind AS target LIMIT 5"
            )


class TestRejectsUnbounded:
    def test_query_must_start_with_match(self):
        with pytest.raises(UnsafeCypher, match="must start with MATCH"):
            validate_cypher("RETURN 1 AS source LIMIT 1")

    def test_query_must_return_something(self):
        with pytest.raises(UnsafeCypher, match="must RETURN"):
            validate_cypher("MATCH (d:Disease) WHERE d.name = $condition LIMIT 5")

    @pytest.mark.parametrize("pattern", ["[*]", "[*2..]", "[:TREATS*]"])
    def test_unbounded_variable_length_is_rejected(self, pattern):
        with pytest.raises(UnsafeCypher, match="upper bound"):
            validate_cypher(
                f"MATCH (d:Disease)-{pattern}-(x) "
                "RETURN d.name AS source, 'x' AS rel, d.kind AS target LIMIT 5"
            )

    def test_oversized_limit_is_rejected_not_silently_capped(self):
        with pytest.raises(UnsafeCypher, match="exceeds maximum"):
            validate_cypher(GOOD.replace("LIMIT 10", "LIMIT 100000"), max_limit=50)

    def test_overlong_query_is_rejected(self):
        with pytest.raises(UnsafeCypher, match="too long"):
            validate_cypher("MATCH (d:Disease) RETURN d.name AS source " + "-- x" * 2000)

    @pytest.mark.parametrize("query", ["", "   ", None])
    def test_empty_is_rejected(self, query):
        with pytest.raises(UnsafeCypher, match="empty query"):
            validate_cypher(query)
