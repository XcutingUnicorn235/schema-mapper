"""The seeded generator: case number -> one customer export of 10 columns and its answer key.

A case is drawn from a stream of SHA-256 blocks seeded with SHA-256("schema-mapper:<case>"), so the same
number gives the same export on every machine and Python version (no ``random``, no ``hash()``).

Each case holds 7 to 9 columns of distinct target fields and 1 to 3 columns that fit none, in a shuffled
order. A column's header is clear (it names one field, in one of four languages or a vendor's style),
vague (it names a group, like "Datum") or opaque ("fld_07"); its four sample values always show which
kind of value it holds. Columns that fit no field are flags, category codes, notes, company names, or
decoys whose values look like a field's (a last-login date, a credit limit, a sales rep's name); a
decoy always has a header that names what it is. :func:`careful_reading` states the reading a careful
person makes, and :func:`make_case` refuses to return a case that reading does not decide.
"""

from __future__ import annotations

import datetime
import hashlib
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import TypeVar

from contract import Field
from plugin import vocab

GENERATOR = "schema-mapper-gen/1"
CASES = 1000
COLUMNS = 10
SAMPLES = 4
SEED_PREFIX = "schema-mapper:"

T = TypeVar("T")
TARGETS = tuple(field for field in Field if field is not Field.UNMAPPED)
EVERY = frozenset(Field)
UNMAPPED_ONLY = frozenset({Field.UNMAPPED})

# What a column's values alone allow, by the kind of column it is. A target field's values fit only that
# field; a decoy's values also fit the field they imitate, so only its header can tell it apart.
LOOKS_LIKE: dict[str, Field] = {
    "last_login": Field.SIGNUP_DATE,
    "credit_limit": Field.LIFETIME_VALUE,
    "loyalty_points": Field.LIFETIME_VALUE,
    "order_count": Field.LIFETIME_VALUE,
    "sales_rep": Field.FULL_NAME,
    "company": Field.FULL_NAME,
    "ref_code": Field.CUSTOMER_ID,
    "promo_code": Field.CUSTOMER_ID,
}
PURE_NOISE = ("flag", "category", "notes")
NOISE_KINDS = tuple(LOOKS_LIKE) + PURE_NOISE


def value_fits(kind: str) -> frozenset[Field]:
    if kind in LOOKS_LIKE:
        return frozenset({LOOKS_LIKE[kind], Field.UNMAPPED})
    if kind in PURE_NOISE:
        return UNMAPPED_ONLY
    return frozenset({Field(kind)})


def careful_reading(header_fits: frozenset[Field], values_fit: frozenset[Field]) -> frozenset[Field]:
    """What a careful reader can conclude about one column: unmapped when its header names something that is
    not a target field or its values fit no field; otherwise the target fields both header and values allow."""
    if header_fits == UNMAPPED_ONLY or values_fit == UNMAPPED_ONLY:
        return UNMAPPED_ONLY
    return (header_fits & values_fit) - UNMAPPED_ONLY


class Stream:
    """Uniform choices from SHA-256 blocks: block i is SHA-256(seed || i as 8 bytes)."""

    def __init__(self, seed: bytes) -> None:
        self._seed = seed
        self._counter = 0

    def _word(self) -> int:
        block = hashlib.sha256(self._seed + self._counter.to_bytes(8, "big")).digest()
        self._counter += 1
        return int.from_bytes(block[:8], "big")

    def below(self, n: int) -> int:
        """A uniform integer in [0, n), by rejection sampling."""
        if n <= 0:
            raise ValueError("below needs a positive bound")
        limit = (1 << 64) - (1 << 64) % n
        while True:
            word = self._word()
            if word < limit:
                return word % n

    def between(self, low: int, high: int) -> int:
        return low + self.below(high - low + 1)

    def percent(self) -> int:
        return self.below(100)

    def choice(self, items: Sequence[T]) -> T:
        return items[self.below(len(items))]

    def shuffled(self, items: Sequence[T]) -> list[T]:
        out = list(items)
        for index in range(len(out) - 1, 0, -1):
            other = self.below(index + 1)
            out[index], out[other] = out[other], out[index]
        return out

    def sample(self, items: Sequence[T], k: int) -> list[T]:
        return self.shuffled(items)[:k]


def seed(case: int) -> bytes:
    return hashlib.sha256(f"{SEED_PREFIX}{case}".encode()).digest()


@dataclass(frozen=True)
class Column:
    header: str
    samples: tuple[str, ...]
    target: Field
    kind: str  # a Field value, or one of NOISE_KINDS
    header_class: str  # clear, vague or opaque
    header_fits: frozenset[Field]


@dataclass(frozen=True)
class Case:
    case: int
    columns: tuple[Column, ...]  # in slot order


# Headers ---------------------------------------------------------------------------------------------------


def styled(header: str, stream: Stream) -> str:
    roll = stream.percent()
    if roll < 55:
        return header
    if roll < 70:
        return header.lower()
    if roll < 85:
        return header.upper()
    snake = re.sub(r"[^\w]+", "_", header).strip("_").lower()
    return snake or header


def vague_groups(field: Field) -> list[tuple[frozenset[Field], tuple[str, ...]]]:
    return [(group, headers) for group, headers in vocab.VAGUE if field in group]


def target_header(field: Field, stream: Stream) -> tuple[str, str, frozenset[Field]]:
    roll = stream.percent()
    if roll < 15:
        return opaque_header(stream), "opaque", EVERY
    groups = vague_groups(field)
    if roll < 40 and groups:
        group, headers = stream.choice(groups)
        return styled(stream.choice(headers), stream), "vague", group
    return styled(stream.choice(vocab.CLEAR[field]), stream), "clear", frozenset({field})


def noise_header(kind: str, stream: Stream) -> tuple[str, str, frozenset[Field]]:
    roll = stream.percent()
    if kind in PURE_NOISE and roll < 25:
        return opaque_header(stream), "opaque", EVERY
    if kind == "category" and roll < 40:
        group, headers = next((g, h) for g, h in vocab.VAGUE if "Code" in h)
        return styled(stream.choice(headers), stream), "vague", group
    return styled(stream.choice(vocab.NOISE_HEADERS[kind]), stream), "clear", UNMAPPED_ONLY


def opaque_header(stream: Stream) -> str:
    return stream.choice(vocab.OPAQUE).format(n=stream.between(1, 40))


# Values ----------------------------------------------------------------------------------------------------


def ascii_fold(text: str) -> str:
    text = text.replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def digits(stream: Stream, count: int) -> str:
    return "".join(str(stream.below(10)) for _ in range(count))


def distinct(make, stream: Stream, count: int = SAMPLES) -> tuple[str, ...]:
    out: list[str] = []
    while len(out) < count:
        value = make(stream)
        if value not in out:
            out.append(value)
    return tuple(out)


def with_repeats(pool: Sequence[str], stream: Stream) -> tuple[str, ...]:
    """Four values from a small set, at least one of them twice: a category, not an identifier."""
    chosen = stream.sample(pool, min(3, len(pool)))
    values = chosen + [stream.choice(chosen)]
    while len(values) < SAMPLES:
        values.append(stream.choice(chosen))
    return tuple(stream.shuffled(values))


def date_text(day: datetime.date, style: str, stream: Stream) -> str:
    m, d, y = day.month, day.day, day.year
    if style == "iso":
        return f"{y:04d}-{m:02d}-{d:02d}"
    if style == "us":
        return f"{m:02d}/{d:02d}/{y:04d}"
    if style == "eu_dot":
        return f"{d:02d}.{m:02d}.{y:04d}"
    if style == "eu_slash":
        return f"{d:02d}/{m:02d}/{y:04d}"
    if style == "text":
        return f"{vocab.MONTHS[m - 1]} {d}, {y}"
    if style == "dmy_text":
        return f"{d:02d}-{vocab.MONTHS[m - 1]}-{y}"
    if style == "stamp":
        return f"{y:04d}-{m:02d}-{d:02d} {stream.below(24):02d}:{stream.below(60):02d}:{stream.below(60):02d}"
    raise ValueError(style)


def dates(stream: Stream, first: datetime.date, last: datetime.date, styles: Sequence[str]) -> tuple[str, ...]:
    style = stream.choice(styles)
    span = last.toordinal() - first.toordinal()
    return distinct(
        lambda s: date_text(datetime.date.fromordinal(first.toordinal() + s.below(span + 1)), style, s), stream
    )


def money(amount_cents: int, style: str) -> str:
    whole, cents = divmod(amount_cents, 100)
    us = f"{whole:,}.{cents:02d}"
    eu = f"{whole:,}".replace(",", ".") + f",{cents:02d}"
    return {
        "plain": f"{whole}.{cents:02d}",
        "dollar": f"${us}",
        "usd": f"{us} USD",
        "euro": f"{eu} €",
        "eur": f"EUR {eu}",
    }[style]


def amounts(stream: Stream, low: int, high: int, round_to: int = 1) -> tuple[str, ...]:
    style = stream.choice(("plain", "dollar", "usd", "euro", "eur"))
    return distinct(lambda s: money(s.between(low, high) // round_to * round_to, style), stream)


def full_name(stream: Stream, style: str) -> str:
    given, surname = stream.choice(vocab.GIVEN), stream.choice(vocab.SURNAMES)
    if style == "last_first":
        return f"{surname}, {given}"
    if style == "initial":
        return f"{given} {chr(ord('A') + stream.below(26))}. {surname}"
    return f"{given} {surname}"


def phone(stream: Stream, style: str) -> str:
    area = stream.choice(vocab.US_AREA_CODES)
    line = f"555-{stream.between(100, 199):04d}"
    if style == "us_paren":
        return f"({area}) {line}"
    if style == "us_dash":
        return f"{area}-{line}"
    if style == "us_dot":
        return f"{area}.{line.replace('-', '.')}"
    if style == "us_intl":
        return f"+1 {area} {line.replace('-', ' ')}"
    if style == "de":
        return f"+49 {stream.choice(('30', '40', '89', '221', '69'))} {digits(stream, 7)}"
    if style == "es":
        return f"+34 9{digits(stream, 2)} {digits(stream, 3)} {digits(stream, 3)}"
    if style == "fr":
        return "0" + str(stream.between(1, 5)) + "".join(f" {digits(stream, 2)}" for _ in range(4))
    raise ValueError(style)


def email(stream: Stream, style: str) -> str:
    given = ascii_fold(stream.choice(vocab.GIVEN)).lower()
    surname = ascii_fold(stream.choice(vocab.SURNAMES)).lower()
    local = {
        "dot": f"{given}.{surname}",
        "initial": f"{given[0]}{surname}",
        "reverse": f"{surname}.{given}",
        "number": f"{given}_{surname}{stream.between(1, 99)}",
    }[style]
    return f"{local}@{stream.choice(vocab.EMAIL_DOMAINS)}"


def street(stream: Stream, style: str) -> str:
    words = vocab.STREET_WORDS
    number = stream.between(1, 240)
    if style == "us":
        unit = f" Apt {stream.between(1, 30)}" if stream.percent() < 20 else ""
        return f"{number} {stream.choice(words['us'])} {stream.choice(words['us_suffix'])}{unit}"
    if style == "de":
        return f"{stream.choice(words['de'])}{stream.choice(words['de_suffix'])} {number}"
    if style == "es":
        return f"{stream.choice(words['es_prefix'])} {stream.choice(words['es'])}, {number}"
    if style == "fr":
        return f"{number} {stream.choice(words['fr_prefix'])} {stream.choice(words['fr'])}"
    raise ValueError(style)


def postal_code(stream: Stream, style: str) -> str:
    if style == "zip4":
        return f"{digits(stream, 5)}-{digits(stream, 4)}"
    return digits(stream, 5)


def ref_code(stream: Stream, style: str) -> str:
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    a, b, c = (stream.choice(letters) for _ in range(3))
    if style == "dashed":
        return f"{a}{b}-{digits(stream, 4)}-{c}"
    return f"{a}{digits(stream, 1)}{b}{digits(stream, 4)}{c}"


def values(kind: str, stream: Stream) -> tuple[str, ...]:
    if kind == Field.CUSTOMER_ID.value:
        size, padded = stream.between(7, 9), stream.percent() < 30
        if padded:
            return distinct(lambda s: "00" + digits(s, size - 2), stream)
        return distinct(lambda s: str(s.between(1, 9)) + digits(s, size - 1), stream)
    if kind == Field.FULL_NAME.value:
        style = stream.choice(("given_first", "given_first", "last_first", "initial"))
        return distinct(lambda s: full_name(s, style), stream)
    if kind == Field.FIRST_NAME.value:
        return tuple(stream.sample(vocab.GIVEN, SAMPLES))
    if kind == Field.LAST_NAME.value:
        return tuple(stream.sample(vocab.SURNAMES, SAMPLES))
    if kind == Field.EMAIL.value:
        style = stream.choice(("dot", "initial", "reverse", "number"))
        return distinct(lambda s: email(s, style), stream)
    if kind == Field.PHONE.value:
        style = stream.choice(("us_paren", "us_dash", "us_dot", "us_intl", "de", "es", "fr"))
        return distinct(lambda s: phone(s, style), stream)
    if kind == Field.BIRTH_DATE.value:
        styles = ("iso", "us", "eu_dot", "eu_slash", "text", "dmy_text")
        return dates(stream, datetime.date(1940, 1, 1), datetime.date(2005, 12, 31), styles)
    if kind == Field.SIGNUP_DATE.value:
        styles = ("iso", "us", "eu_dot", "eu_slash", "text", "dmy_text", "stamp")
        return dates(stream, datetime.date(2015, 1, 1), datetime.date(2026, 9, 30), styles)
    if kind == Field.STREET.value:
        style = stream.choice(("us", "us", "de", "es", "fr"))
        return distinct(lambda s: street(s, style), stream)
    if kind == Field.CITY.value:
        return tuple(stream.sample(vocab.CITIES, SAMPLES))
    if kind == Field.STATE.value:
        pool = vocab.STATE_CODES if stream.percent() < 70 else vocab.STATE_NAMES
        return tuple(stream.sample(pool, SAMPLES))
    if kind == Field.POSTAL_CODE.value:
        style = "zip4" if stream.percent() < 30 else "five"
        return distinct(lambda s: postal_code(s, style), stream)
    if kind == Field.COUNTRY.value:
        pool = vocab.COUNTRIES[stream.choice(("english", "iso3", "native"))]
        return tuple(stream.shuffled([pool[0]] + [stream.choice(pool) for _ in range(SAMPLES - 1)]))
    if kind == Field.LIFETIME_VALUE.value:
        return amounts(stream, 1500, 2_500_000)
    if kind == "last_login":
        styles = ("iso", "us", "eu_dot", "text", "stamp")
        return dates(stream, datetime.date(2024, 1, 1), datetime.date(2026, 9, 30), styles)
    if kind == "credit_limit":
        return amounts(stream, 50_000, 2_000_000, round_to=50_000)
    if kind == "sales_rep":
        return distinct(lambda s: full_name(s, "given_first"), stream)
    if kind == "loyalty_points":
        return distinct(lambda s: str(s.between(0, 9999)), stream)
    if kind == "order_count":
        return distinct(lambda s: str(s.between(1, 48)), stream)
    if kind == "ref_code":
        style = stream.choice(("dashed", "packed"))
        return distinct(lambda s: ref_code(s, style), stream)
    if kind == "promo_code":
        return tuple(stream.sample(vocab.PROMO_CODES, SAMPLES))
    if kind == "company":
        return tuple(stream.sample(vocab.COMPANIES, SAMPLES))
    if kind == "flag":
        pair = stream.choice(vocab.FLAGS)
        return tuple(stream.shuffled([pair[0], pair[1]] + [stream.choice(pair) for _ in range(SAMPLES - 2)]))
    if kind == "category":
        return with_repeats(stream.choice(vocab.CATEGORIES), stream)
    if kind == "notes":
        return tuple(stream.sample(vocab.NOTES, SAMPLES))
    raise ValueError(f"unknown column kind {kind!r}")


# Cases -----------------------------------------------------------------------------------------------------


def normalized(header: str) -> str:
    """A header without case, spaces and punctuation, to tell two headers apart; a header of punctuation only
    ("#") is kept as it is."""
    return re.sub(r"[\W_]+", "", header.casefold()) or header.strip()


def make_case(case: int) -> Case:
    if not 0 <= case < CASES:
        raise ValueError(f"case must be from 0 to {CASES - 1}, not {case}")
    stream = Stream(seed(case))
    unmapped = stream.between(1, 3)
    fields = stream.sample(TARGETS, COLUMNS - unmapped)
    noise = stream.sample(NOISE_KINDS, unmapped)
    planned = [(field.value, field) for field in fields] + [(kind, Field.UNMAPPED) for kind in noise]
    columns: list[Column] = []
    seen: set[str] = set()
    for kind, target in planned:
        while True:
            if target is Field.UNMAPPED:
                header, header_class, fits = noise_header(kind, stream)
            else:
                header, header_class, fits = target_header(target, stream)
            if header.strip() and normalized(header) not in seen:
                seen.add(normalized(header))
                break
        columns.append(Column(header, values(kind, stream), target, kind, header_class, fits))
    made = Case(case, tuple(stream.shuffled(columns)))
    problems = undecided(made)
    if problems:
        raise RuntimeError(f"case {case} is not decidable: {problems}")
    return made


def undecided(made: Case) -> list[str]:
    """Every way a case falls short of one right answer a careful reader can reach."""
    problems = []
    for index, column in enumerate(made.columns):
        reading = careful_reading(column.header_fits, value_fits(column.kind))
        if reading != frozenset({column.target}):
            problems.append(f"column {index + 1} ({column.header!r}) reads as {sorted(f.value for f in reading)}")
    targets = [column.target for column in made.columns if column.target is not Field.UNMAPPED]
    if len(targets) != len(set(targets)):
        problems.append("a target field is used twice")
    if not 1 <= COLUMNS - len(targets) <= 3:
        problems.append("a case must hold 1 to 3 unmapped columns")
    if len({normalized(column.header) for column in made.columns}) != COLUMNS:
        problems.append("two headers are the same")
    return problems


@cache
def case(number: int) -> Case:
    return make_case(number)


# Hints -----------------------------------------------------------------------------------------------------


def shape(value: str) -> str:
    """9 per digit; A for a run of letters that starts upper case, a for one that starts lower case; rest kept."""
    out: list[str] = []
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


def profile(samples: Sequence[str]) -> tuple[list[str], str, float]:
    shapes: list[str] = []
    for value in samples:
        if shape(value) not in shapes:
            shapes.append(shape(value))
    lengths = [len(value) for value in samples]
    characters = sum(lengths)
    share = round(sum(char.isdigit() for value in samples for char in value) / characters, 2) if characters else 0.0
    return shapes, f"{min(lengths)}-{max(lengths)}", share
