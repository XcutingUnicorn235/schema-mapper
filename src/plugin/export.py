"""The two tools: read a case's export (what the model sees), and pin its answer key (what it never sees)."""

from __future__ import annotations

from pathlib import Path

from contract import CaseInput, Column, ExportOutput, Key, PinOutput, Profile, Slot
from plugin import generator

SLOTS = list(Slot)


def read_export(given: CaseInput, workspace: Path) -> ExportOutput:
    made = generator.case(given.case)
    columns = []
    for slot, column in zip(SLOTS, made.columns, strict=True):
        shapes, length, share = generator.profile(column.samples)
        columns.append(
            Column(
                slot=slot,
                header=column.header,
                samples=list(column.samples),
                profile=Profile(shapes=shapes, length=length, digit_share=share),
            )
        )
    return ExportOutput(case=given.case, columns=columns)


def pin_mapping(given: CaseInput, workspace: Path) -> PinOutput:
    made = generator.case(given.case)
    keys = [Key(slot=slot, target=column.target) for slot, column in zip(SLOTS, made.columns, strict=True)]
    return PinOutput(case=given.case, generator=generator.GENERATOR, keys=keys)
