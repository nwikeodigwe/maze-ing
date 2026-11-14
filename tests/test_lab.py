"""Tests for the lab score calculation."""

from datetime import timedelta

from src.rooms.lab_d2_002 import LabD2002


def _score(exploration, assembly):
    # ``__calculate_score`` uses only class constants and its arguments, so an
    # uninitialised instance is enough and avoids constructing a database/state.
    return LabD2002._LabD2002__calculate_score(object.__new__(LabD2002), exploration, assembly)


def test_zero_time_scores_base():
    assert _score(timedelta(0), timedelta(0)) == 1000


def test_exploration_time_reduces_score():
    assert _score(timedelta(minutes=10), timedelta(0)) == 880


def test_assembly_time_reduces_score():
    assert _score(timedelta(0), timedelta(minutes=5)) == 980


def test_exploration_and_assembly_are_weighted_together():
    assert _score(timedelta(minutes=10), timedelta(minutes=5)) == 860


def test_score_never_drops_below_zero():
    assert _score(timedelta(hours=10), timedelta(hours=10)) == 0
