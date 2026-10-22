"""map-columns: the submitted mapping against the generator's answer key.

The verdict is valid only when all 10 columns are mapped right. The score is chance-corrected: the
best answer that reads nothing is "every column unmapped", which gets the case's u unmapped columns right
out of 10. A column put on a wrong field also costs half a column more, because in an import a wrong
field is worse than no field: it silently fills the target with another column's data, while an
unmapped column is left for someone to look at. So

    score = max(0, (right - wrong_field / 2 - u) / (10 - u))

Every column unmapped scores 0, any constant field or random fields score 0 (or very near it), and the
answer key itself scores 1. Plain accuracy would give "every column unmapped" 0.1 to 0.3, and would let
an answer that guesses a field for every column lose nothing for guessing.
"""

from collections import Counter
from dataclasses import asdict

from contract import Field

from . import rules
from .checks import constraint, failed, result
from .pin import key_constraints

WRONG_FIELD_COST = 0.5


def chosen(output):
    """The submitted field of every slot: the output's fields col01 to col10 are named after the slots."""
    fields = asdict(output)
    return {slot: fields[slot.value] for slot in rules.SLOTS}


def verify_task(arguments, output, reference, workspace):
    # Gates: a broken answer key or an answer to another case is not compared at all.
    gates = key_constraints(arguments.case, reference)
    gates.append(
        constraint(
            "same-case",
            "The output answers the task's case",
            output.case == arguments.case,
            arguments.case,
            output.case,
        )
    )
    broken = failed(gates)
    if broken:
        return result(False, broken[0]["constraint"] + ": it does not hold", score=0.0, constraints=gates)

    truth = {entry.slot: entry.target for entry in reference.keys}
    answer = chosen(output)
    wrong = [slot for slot in rules.SLOTS if answer[slot] != truth[slot]]
    on_wrong_field = [slot for slot in wrong if answer[slot] is not Field.UNMAPPED]
    left_out = [slot for slot in wrong if answer[slot] is Field.UNMAPPED]
    forced = [slot for slot in on_wrong_field if truth[slot] is Field.UNMAPPED]
    uses = Counter(field for field in answer.values() if field is not Field.UNMAPPED)
    twice = sorted(field.value for field, count in uses.items() if count > 1)

    columns = len(rules.SLOTS)
    unmapped = sum(target is Field.UNMAPPED for target in truth.values())
    right = columns - len(wrong)
    score = max(0.0, (right - WRONG_FIELD_COST * len(on_wrong_field) - unmapped) / (columns - unmapped))
    constraints = gates + [
        constraint(
            "columns-right",
            "Every column is mapped to the field it holds, or unmapped when it fits none",
            not wrong,
            {slot.value: truth[slot].value for slot in wrong},
            {slot.value: answer[slot].value for slot in wrong},
        ),
        constraint("field-once", "No field is used for two columns", not twice, [], twice),
        constraint(
            "unmapped-kept",
            "No column that fits no field is put on a field",
            not forced,
            [],
            [slot.value for slot in forced],
        ),
    ]
    message = (
        f"{right} of 10 columns right: {len(on_wrong_field)} on a wrong field "
        f"({len(forced)} of them fitting no field), {len(left_out)} left unmapped, "
        f"{len(twice)} {'field' if len(twice) == 1 else 'fields'} used twice"
    )
    return result(
        not wrong,
        message,
        score=round(score, 4),
        constraints=constraints,
        right=right,
        on_wrong_field=len(on_wrong_field),
        forced_unmappable=len(forced),
        left_unmapped=len(left_out),
        fields_used_twice=len(twice),
        unmapped_in_key=unmapped,
    )
