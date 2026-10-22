"""read_export: what the model is shown must be one whole export, in slot order, with honest hints."""

from . import rules
from .checks import result


def verify_input(value):
    if not rules.in_range(value.case):
        return result(False, f"case must be from 0 to {rules.CASES - 1}, not {value.case}")
    return result(True, "the case exists")


def verify_output(input_value, output_value, workspace):
    if output_value.case != input_value.case:
        return result(False, f"read case {output_value.case}, not the asked {input_value.case}")
    if [column.slot for column in output_value.columns] != rules.SLOTS:
        return result(False, "the export must hold exactly the columns col01 to col10, in order")
    headers = [column.header.strip().casefold() for column in output_value.columns]
    if not all(headers) or len(set(headers)) != len(headers):
        return result(False, "every column must have its own, non-blank header")
    for column in output_value.columns:
        name = column.slot.value
        if len(column.samples) != rules.SAMPLES or not all(value.strip() for value in column.samples):
            return result(False, f"column {name} must show {rules.SAMPLES} non-blank sample values")
        shapes, length, share = rules.profile(column.samples)
        hint = column.profile
        if hint.shapes != shapes or hint.length != length or hint.digit_share != share:
            return result(False, f"column {name}'s profile does not match its samples")
    return result(True, f"case {output_value.case}: 10 columns in slot order")
