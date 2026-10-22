"""pin_mapping: the answer key must come from the pinned generator and have a case's fixed shape."""

from collections import Counter

from contract import Field

from . import rules
from .checks import constraint, failed, result


def key_constraints(case, key):
    """The answer key's own checks: this case, the pinned generator, one entry per slot, each field at most
    once, 1 to 3 unmapped columns."""
    if key is None:
        return [constraint("answer-key", "The task has an answer key", False, "pinned", "missing")]
    slots = [entry.slot for entry in key.keys]
    targets = [entry.target for entry in key.keys]
    twice = sorted(
        field.value for field, count in Counter(targets).items() if field is not Field.UNMAPPED and count > 1
    )
    unmapped = targets.count(Field.UNMAPPED)
    return [
        constraint("key-case", "The answer key is for the task's case", key.case == case, case, key.case),
        constraint(
            "key-generator",
            "The answer key comes from the pinned generator version",
            key.generator == rules.GENERATOR,
            rules.GENERATOR,
            key.generator,
        ),
        constraint(
            "key-slots", "The answer key has one entry per slot, col01 to col10, in order", slots == rules.SLOTS
        ),
        constraint("key-fields", "The answer key uses every target field at most once", not twice, [], twice),
        constraint(
            "key-unmapped",
            "The answer key leaves 1 to 3 columns unmapped",
            rules.MIN_UNMAPPED <= unmapped <= rules.MAX_UNMAPPED,
            f"{rules.MIN_UNMAPPED}-{rules.MAX_UNMAPPED}",
            unmapped,
        ),
    ]


def verify_input(value):
    if not rules.in_range(value.case):
        return result(False, f"case must be from 0 to {rules.CASES - 1}, not {value.case}")
    return result(True, "the case exists")


def verify_output(input_value, output_value, workspace):
    problems = failed(key_constraints(input_value.case, output_value))
    if problems:
        return result(False, problems[0]["constraint"] + ": it does not hold", constraints=problems)
    return result(True, f"answer key for case {input_value.case} is pinned")
