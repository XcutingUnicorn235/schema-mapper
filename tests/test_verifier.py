"""The verifier on contract instances built the way NanoAgent's sandbox builds them: from plain JSON."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from agents import all_unmapped, oracle
from slimconfig import build_output, plain_output

import verifier
from contract import CaseInput, ExportOutput, Field, MappingOutput, PinOutput, Slot
from plugin.export import pin_mapping, read_export

CASE = 7


def sandboxed(value, cls):
    return build_output(plain_output(value), cls)


def given(case: int = CASE) -> CaseInput:
    return build_output({"case": case}, CaseInput)


def key(tmp_path: Path, case: int = CASE) -> PinOutput:
    return sandboxed(pin_mapping(given(case), tmp_path), PinOutput)


def shown(tmp_path: Path, case: int = CASE) -> ExportOutput:
    return sandboxed(read_export(given(case), tmp_path), ExportOutput)


def answer(mapping: dict[str, str], case: int = CASE) -> MappingOutput:
    return build_output({"case": case, **mapping}, MappingOutput)


def truth(reference: PinOutput) -> dict[str, str]:
    return oracle(plain_output(reference))


def verdict(output, reference, tmp_path: Path, case: int = CASE):
    return verifier.verify_task("map-columns", given(case), output, reference, str(tmp_path))


def slots_where(reference: PinOutput, mapped: bool) -> list[str]:
    return [entry.slot.value for entry in reference.keys if (entry.target is not Field.UNMAPPED) == mapped]


def test_oracle_answer_scores_one(tmp_path: Path) -> None:
    for case in range(25):
        reference = key(tmp_path, case)
        result = verdict(answer(truth(reference), case), reference, tmp_path, case)
        assert result["valid"] is True and result["score"] == 1.0
        assert result["message"].startswith("10 of 10 columns right: 0 on a wrong field")
        assert all(item["ok"] for item in result["details"]["constraints"])


def test_every_column_unmapped_scores_zero(tmp_path: Path) -> None:
    reference = key(tmp_path)
    result = verdict(answer(all_unmapped({})), reference, tmp_path)
    assert result["valid"] is False and result["score"] == 0.0
    assert result["details"]["right"] == result["details"]["unmapped_in_key"]


def test_a_column_left_unmapped_is_invalid_with_partial_credit(tmp_path: Path) -> None:
    reference = key(tmp_path)
    mapping = truth(reference)
    mapped = slots_where(reference, mapped=True)
    mapping[mapped[0]] = Field.UNMAPPED.value
    result = verdict(answer(mapping), reference, tmp_path)
    unmapped = result["details"]["unmapped_in_key"]
    assert result["valid"] is False
    assert result["score"] == round((9 - unmapped) / (10 - unmapped), 4)
    assert result["details"]["left_unmapped"] == 1
    assert [item["id"] for item in result["details"]["constraints"] if not item["ok"]] == ["columns-right"]


def test_a_wrong_field_costs_more_than_leaving_a_column_unmapped(tmp_path: Path) -> None:
    reference = key(tmp_path)
    mapped = slots_where(reference, mapped=True)
    left_out = truth(reference) | {mapped[0]: Field.UNMAPPED.value}
    swapped = truth(reference) | {mapped[0]: truth(reference)[mapped[1]], mapped[1]: truth(reference)[mapped[0]]}
    unmapped = len(slots_where(reference, mapped=False))
    assert verdict(answer(left_out), reference, tmp_path)["score"] == round((9 - unmapped) / (10 - unmapped), 4)
    result = verdict(answer(swapped), reference, tmp_path)
    assert result["valid"] is False
    assert result["score"] == round((8 - 1 - unmapped) / (10 - unmapped), 4)
    assert result["details"]["on_wrong_field"] == 2


def test_forcing_an_unmappable_column_onto_a_field_breaks_two_rules(tmp_path: Path) -> None:
    reference = key(tmp_path)
    mapping = truth(reference)
    noise = slots_where(reference, mapped=False)[0]
    mapping[noise] = mapping[slots_where(reference, mapped=True)[0]]  # the same field twice
    result = verdict(answer(mapping), reference, tmp_path)
    failing = [item["id"] for item in result["details"]["constraints"] if not item["ok"]]
    assert result["valid"] is False
    assert failing == ["columns-right", "field-once", "unmapped-kept"]
    assert result["details"]["forced_unmappable"] == 1 and result["details"]["fields_used_twice"] == 1
    unmapped = result["details"]["unmapped_in_key"]
    assert result["score"] == round((9 - 0.5 - unmapped) / (10 - unmapped), 4)


@pytest.mark.parametrize("field", list(Field), ids=[field.value for field in Field])
def test_one_field_for_every_column_scores_zero(tmp_path: Path, field: Field) -> None:
    for case in range(10):
        reference = key(tmp_path, case)
        result = verdict(answer({slot.value: field.value for slot in Slot}, case), reference, tmp_path, case)
        assert result["valid"] is False and result["score"] == 0.0


def test_an_answer_to_another_case_scores_zero(tmp_path: Path) -> None:
    reference = key(tmp_path)
    result = verdict(answer(truth(reference), case=CASE + 1), reference, tmp_path)
    assert result["valid"] is False and result["score"] == 0.0
    assert result["message"].startswith("The output answers the task's case")


def test_a_missing_answer_key_scores_zero(tmp_path: Path) -> None:
    result = verdict(answer(all_unmapped({})), None, tmp_path)
    assert result["valid"] is False and result["score"] == 0.0
    assert "answer key" in result["message"]


@pytest.mark.parametrize(
    "broken",
    [{"col01": "zip"}, {"col01": None}, {"col11": "email"}, {"case": "7"}],
    ids=["unknown-field", "null-field", "extra-column", "case-as-text"],
)
def test_a_malformed_answer_never_reaches_the_verifier(broken: dict) -> None:
    mapping = {"case": CASE, **all_unmapped({}), **broken}
    with pytest.raises((TypeError, ValueError)):
        build_output(mapping, MappingOutput)


def test_a_missing_column_never_reaches_the_verifier() -> None:
    mapping = all_unmapped({})
    del mapping["col10"]
    with pytest.raises((TypeError, ValueError)):
        build_output({"case": CASE, **mapping}, MappingOutput)


def tampered(reference: PinOutput, **changes) -> PinOutput:
    return sandboxed(replace(reference, **changes), PinOutput)


def with_targets(reference: PinOutput, targets: list[Field]) -> list:
    return [replace(entry, target=target) for entry, target in zip(reference.keys, targets, strict=True)]


@pytest.mark.parametrize(
    "change, failing",
    [
        (lambda r: {"generator": "schema-mapper-gen/0"}, "key-generator"),
        (lambda r: {"case": CASE + 1}, "key-case"),
        (lambda r: {"keys": list(reversed(r.keys))}, "key-slots"),
        (lambda r: {"keys": r.keys[:-1]}, "key-slots"),
        (
            lambda r: {
                "keys": with_targets(r, [Field.EMAIL, Field.EMAIL] + [Field.UNMAPPED] + [e.target for e in r.keys[3:]])
            },
            "key-fields",
        ),
        (lambda r: {"keys": with_targets(r, [Field.UNMAPPED] * 10)}, "key-unmapped"),
        (lambda r: {"keys": with_targets(r, list(Field)[:10])}, "key-unmapped"),
    ],
    ids=[
        "other-generator",
        "other-case",
        "reordered",
        "a-slot-missing",
        "field-twice",
        "all-unmapped",
        "none-unmapped",
    ],
)
def test_a_tampered_answer_key_is_refused(tmp_path: Path, change, failing: str) -> None:
    reference = key(tmp_path)
    broken = tampered(reference, **change(reference))
    result = verdict(answer(truth(reference)), broken, tmp_path)
    assert result["valid"] is False and result["score"] == 0.0
    assert failing in [item["id"] for item in result["details"]["constraints"] if not item["ok"]]
    assert verifier.verify_output("pin_mapping", given(), broken, str(tmp_path))["valid"] is False


def test_the_pinned_key_passes_its_own_check(tmp_path: Path) -> None:
    for case in (0, 1, 500, 999):
        assert verifier.verify_output("pin_mapping", given(case), key(tmp_path, case), str(tmp_path))["valid"] is True


@pytest.mark.parametrize("tool", ["read_export", "pin_mapping"])
def test_inputs_must_name_an_existing_case(tool: str) -> None:
    assert verifier.verify_input(tool, given(0))["valid"] is True
    assert verifier.verify_input(tool, given(999))["valid"] is True
    assert verifier.verify_input(tool, given(-1))["valid"] is False
    assert verifier.verify_input(tool, given(1000))["valid"] is False


def test_read_export_output_is_checked(tmp_path: Path) -> None:
    export = shown(tmp_path)
    assert verifier.verify_output("read_export", given(), export, str(tmp_path))["valid"] is True
    columns = export.columns
    first = columns[0]
    cases = {
        "other case": replace(export, case=CASE + 1),
        "a column missing": replace(export, columns=columns[:-1]),
        "slots reordered": replace(export, columns=[columns[1], columns[0]] + columns[2:]),
        "blank header": replace(export, columns=[replace(first, header=" ")] + columns[1:]),
        "same header twice": replace(export, columns=[replace(first, header=columns[1].header.upper())] + columns[1:]),
        "three samples": replace(export, columns=[replace(first, samples=first.samples[:3])] + columns[1:]),
        "blank sample": replace(export, columns=[replace(first, samples=[""] + first.samples[1:])] + columns[1:]),
        "changed sample": replace(
            export, columns=[replace(first, samples=["##########"] + first.samples[1:])] + columns[1:]
        ),
        "fabricated hint": replace(
            export, columns=[replace(first, profile=replace(first.profile, digit_share=0.5))] + columns[1:]
        ),
    }
    for name, bad in cases.items():
        result = verifier.verify_output("read_export", given(), sandboxed(bad, ExportOutput), str(tmp_path))
        assert result["valid"] is False, name


def test_the_verdict_is_deterministic_and_small(tmp_path: Path) -> None:
    reference = key(tmp_path)
    mapping = {slot.value: Field.EMAIL.value for slot in Slot}  # every column wrong: the longest verdict
    first = json.dumps(verdict(answer(mapping), reference, tmp_path), sort_keys=True)
    second = json.dumps(verdict(answer(mapping), reference, tmp_path), sort_keys=True)
    assert first == second
    assert len(first) < 8000, "the verdict lands in the chat's context: keep it small"
