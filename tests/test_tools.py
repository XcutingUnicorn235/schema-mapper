from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest
from slimconfig import plain_output

from contract import CaseInput, Field, Slot
from plugin import generator
from plugin.export import pin_mapping, read_export

# SHA-256 of a case's export and key as JSON: a change to the generator, its vocabularies or its stream
# changes these, and must come with a new GENERATOR version.
FINGERPRINTS = {
    0: "f080ea6e788ba7a0f5e7bbcbac6aad86026203ce1c70a65ce27ad8b8cd5d11cd",
    1: "cf19e94d87005652e568eda4fa6eabfcf5cdacb71869a6f98ac021f000c2e21e",
    999: "13553f12b73282123baed52d258dcb5e82b7aed1257a7040adf1b24e75aff0d4",
}


def fingerprint(case: int, workspace: Path) -> str:
    both = {
        "export": plain_output(read_export(CaseInput(case=case), workspace)),
        "key": plain_output(pin_mapping(CaseInput(case=case), workspace)),
    }
    return hashlib.sha256(json.dumps(both, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def test_read_export_shows_one_whole_export_in_slot_order(tmp_path: Path) -> None:
    output = read_export(CaseInput(case=4), tmp_path)
    assert output.case == 4
    assert [column.slot for column in output.columns] == list(Slot)
    for column in output.columns:
        assert len(column.samples) == generator.SAMPLES and all(column.samples)
        shapes, length, share = generator.profile(column.samples)
        assert (column.profile.shapes, column.profile.length, column.profile.digit_share) == (shapes, length, share)
    assert not list(tmp_path.iterdir()), "reading an export writes nothing"


def test_read_export_never_shows_the_answer(tmp_path: Path) -> None:
    for case in range(50):
        shown = plain_output(read_export(CaseInput(case=case), tmp_path))
        text = json.dumps(shown, ensure_ascii=False)
        assert "unmapped" not in text and "target" not in text and "kind" not in text
        assert generator.GENERATOR not in text
        assert generator.seed(case).hex() not in text
        # The only whole number in what the model sees is the case it asked for, so the decide runner
        # never has to choose which number to copy into the output.
        numbers = [shown["case"]] + [
            value for column in shown["columns"] for value in column["profile"].values() if isinstance(value, int)
        ]
        assert numbers == [case]


def test_pin_mapping_keys_one_case_in_slot_order(tmp_path: Path) -> None:
    key = pin_mapping(CaseInput(case=4), tmp_path)
    assert key.case == 4 and key.generator == generator.GENERATOR
    assert [entry.slot for entry in key.keys] == list(Slot)


def test_every_case_has_the_fixed_shape_and_a_reading_that_decides_it() -> None:
    unmapped = Counter()
    for case in range(generator.CASES):
        made = generator.case(case)
        assert generator.undecided(made) == [], case
        targets = [column.target for column in made.columns]
        unmapped[targets.count(Field.UNMAPPED)] += 1
    assert set(unmapped) == {1, 2, 3}
    assert min(unmapped.values()) > generator.CASES // 4


def test_cases_are_fixed_by_their_number(tmp_path: Path) -> None:
    first = [fingerprint(case, tmp_path) for case in range(20)]
    generator.case.cache_clear()
    assert [fingerprint(case, tmp_path) for case in range(20)] == first
    assert len(set(first)) == 20


def test_the_pinned_generator_still_makes_the_same_cases(tmp_path: Path) -> None:
    assert {case: fingerprint(case, tmp_path) for case in FINGERPRINTS} == FINGERPRINTS


@pytest.mark.parametrize("case", [-1, generator.CASES])
def test_refuses_a_case_out_of_range(tmp_path: Path, case: int) -> None:
    with pytest.raises(ValueError, match="case must be from 0"):
        read_export(CaseInput(case=case), tmp_path)
    with pytest.raises(ValueError, match="case must be from 0"):
        pin_mapping(CaseInput(case=case), tmp_path)
