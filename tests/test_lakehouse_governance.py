"""Lakehouse SQL guardrails (validate_sql_query)."""
import pytest

from packages.lakehouse.governance import validate_sql_query
from tests.fixtures.adversarial_matrix import LAKEHOUSE_SQL_CASES


@pytest.mark.parametrize("case", LAKEHOUSE_SQL_CASES, ids=lambda c: c.case_id)
def test_lakehouse_sql_guardrails(case):
    ok, _msg = validate_sql_query(case.query)
    assert ok == case.should_pass
