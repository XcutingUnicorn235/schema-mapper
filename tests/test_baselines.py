"""Trivial agents, two rule baselines and a naive verifier, scored over many cases.

An answer that cannot read the export must score about 0 here, and the key itself 1. The two rule
baselines show the task is not solved by a rule: a header lookup in a small dictionary of the obvious
names, and regular expressions on the values. The naive verifier is what a quick check would use, plain
accuracy against the key; the numbers show what it would reward instead.
"""

from __future__ import annotations

import random
from pathlib import Path
from statistics import mean

import agents
from slimconfig import plain_output
from test_verifier import answer, key, shown, verdict

from contract import Field

CASES = range(200)


def scores(tmp_path: Path, agent, cases=CASES) -> list[float]:
    out = []
    for case in cases:
        reference = key(tmp_path, case)
        mapping = agent(plain_output(shown(tmp_path, case)))
        out.append(verdict(answer(mapping, case), reference, tmp_path, case)["score"])
    return out


def oracle_scores(tmp_path: Path) -> list[float]:
    out = []
    for case in CASES:
        reference = key(tmp_path, case)
        out.append(verdict(answer(agents.oracle(plain_output(reference)), case), reference, tmp_path, case)["score"])
    return out


def naive_accuracy(tmp_path: Path, agent) -> float:
    out = []
    for case in CASES:
        truth = agents.oracle(plain_output(key(tmp_path, case)))
        mapping = agent(plain_output(shown(tmp_path, case)))
        out.append(mean(mapping[slot] == truth[slot] for slot in agents.SLOTS))
    return mean(out)


def test_the_oracle_scores_one_and_every_column_unmapped_zero(tmp_path: Path) -> None:
    assert oracle_scores(tmp_path) == [1.0] * len(CASES)
    assert scores(tmp_path, agents.all_unmapped) == [0.0] * len(CASES)


def test_any_constant_field_scores_zero(tmp_path: Path) -> None:
    for field in Field:
        assert max(scores(tmp_path, agents.constant(field), range(50))) == 0.0, field


def test_random_fields_score_near_zero(tmp_path: Path) -> None:
    rng = random.Random(580)
    assert mean(scores(tmp_path, agents.random_fields(rng))) < 0.02


def test_the_header_only_rule_baseline_stays_far_below_one(tmp_path: Path) -> None:
    results = scores(tmp_path, agents.header_only)
    assert 0.0 < mean(results) < 0.2
    assert sum(result == 1.0 for result in results) == 0


def test_the_value_pattern_baseline_stays_below_one(tmp_path: Path) -> None:
    results = scores(tmp_path, agents.value_patterns)
    assert mean(results) < 0.7
    assert sum(result == 1.0 for result in results) < len(CASES) // 20


def test_plain_accuracy_would_reward_leaving_everything_unmapped(tmp_path: Path) -> None:
    accuracy = naive_accuracy(tmp_path, agents.all_unmapped)
    assert 0.15 < accuracy < 0.25  # 1 to 3 unmapped columns out of 10
    assert naive_accuracy(tmp_path, agents.header_only) > accuracy  # and barely more for a header lookup
