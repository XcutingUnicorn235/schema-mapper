"""The verifier restates the plugin's rules; they must agree."""

from __future__ import annotations

import random

from contract import Field, Slot
from plugin import generator
from verifier import rules


def test_constants_agree() -> None:
    assert generator.GENERATOR == rules.GENERATOR
    assert generator.CASES == rules.CASES
    assert generator.SAMPLES == rules.SAMPLES
    assert rules.SLOTS == list(Slot) and len(rules.SLOTS) == generator.COLUMNS
    assert list(generator.TARGETS) == rules.TARGETS
    assert Field.UNMAPPED not in rules.TARGETS


def test_the_case_range_agrees() -> None:
    for case in (-1, 0, 1, 998, 999, 1000):
        assert rules.in_range(case) == (0 <= case < generator.CASES)


def test_the_profile_agrees() -> None:
    rng = random.Random(1)
    alphabet = "abcXYZ019 -/.,@+()$€éÜß#_"
    for _ in range(500):
        samples = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 25))) for _ in range(4)]
        assert generator.profile(samples) == rules.profile(samples)
    for case in range(100):
        for column in generator.case(case).columns:
            assert generator.profile(column.samples) == rules.profile(column.samples)
