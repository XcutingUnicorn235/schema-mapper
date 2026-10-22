"""The plugin's fixed rules, restated here because the verifier may not import the plugin's own code.

They must agree with src/plugin/generator.py; tests/test_rules.py checks that they do.
"""

from contract import Field, Slot

GENERATOR = "schema-mapper-gen/1"
CASES = 1000
SAMPLES = 4
MIN_UNMAPPED = 1
MAX_UNMAPPED = 3
SLOTS = list(Slot)
TARGETS = [field for field in Field if field is not Field.UNMAPPED]


def in_range(case):
    return 0 <= case < CASES


def shape(value):
    """9 per digit; A for a run of letters that starts upper case, a for one that starts lower case; rest kept."""
    out = []
    in_letters = False
    for char in value:
        if char.isdigit():
            out.append("9")
            in_letters = False
        elif char.isalpha():
            if not in_letters:
                out.append("A" if char.isupper() else "a")
            in_letters = True
        else:
            out.append(char)
            in_letters = False
    return "".join(out)


def profile(samples):
    """The column's hints: distinct sample shapes in sample order, the length range, the share of digits."""
    shapes = []
    for value in samples:
        if shape(value) not in shapes:
            shapes.append(shape(value))
    lengths = [len(value) for value in samples]
    characters = sum(lengths)
    share = round(sum(char.isdigit() for value in samples for char in value) / characters, 2) if characters else 0.0
    return shapes, f"{min(lengths)}-{max(lengths)}", share
