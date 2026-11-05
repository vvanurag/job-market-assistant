from datetime import date, datetime
from decimal import Decimal

from jobmarket.portability import compare_rows, normalise


def test_values_from_either_engine_normalise_the_same():
    assert normalise(True) == "true"
    assert normalise(None) == "∅"
    assert normalise(date(2026, 11, 5)) == normalise(datetime(2026, 11, 5)) == "2026-11-05"
    assert normalise(Decimal("14")) == normalise(14) == normalise(14.0) == "14"


def test_identical_rows_in_any_order_match():
    result = compare_rows("t", [("a", 1), ("b", 2)], [("b", Decimal(2)), ("a", 1)])
    assert result.identical
    assert (result.rows_a, result.rows_b) == (2, 2)


def test_differences_are_counted_both_ways_with_examples():
    result = compare_rows("t", [("a", 1), ("b", 2)], [("a", 1), ("c", 3), ("c", 3)])
    assert not result.identical
    assert (result.only_in_a, result.only_in_b) == (1, 2)
    assert any("b" in e for e in result.examples)


def test_duplicate_rows_are_compared_as_counts():
    assert not compare_rows("t", [("a",), ("a",)], [("a",)]).identical
