"""The generator's promises: every case has exactly one right answer a careful reader can reach, the
header alone does not give it away, and nothing in what the model sees encodes it."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from itertools import combinations

from contract import Field
from plugin import generator, vocab
from plugin.generator import EVERY, UNMAPPED_ONLY, Stream, careful_reading, value_fits

ALL = range(generator.CASES)


def every_column():
    for case in ALL:
        yield from generator.case(case).columns


def test_the_stream_is_seeded_by_a_stable_hash_and_is_uniform() -> None:
    assert generator.seed(12) == hashlib.sha256(b"schema-mapper:12").digest()
    first, again = Stream(generator.seed(3)), Stream(generator.seed(3))
    assert [first.below(1000) for _ in range(50)] == [again.below(1000) for _ in range(50)]
    stream = Stream(b"uniform")
    counts = Counter(stream.below(10) for _ in range(20_000))
    assert set(counts) == set(range(10)) and max(counts.values()) - min(counts.values()) < 300


def test_the_word_lists_never_overlap() -> None:
    lists = {
        "given": set(vocab.GIVEN),
        "surnames": set(vocab.SURNAMES),
        "cities": set(vocab.CITIES),
        "state names": set(vocab.STATE_NAMES),
        "state codes": set(vocab.STATE_CODES),
        "countries": {name for names in vocab.COUNTRIES.values() for name in names},
    }
    for (a, left), (b, right) in combinations(lists.items(), 2):
        assert not left & right, (a, b, left & right)


def test_no_header_means_two_different_things() -> None:
    meanings: dict[str, frozenset] = {}
    entries = [(header, frozenset({field})) for field, headers in vocab.CLEAR.items() for header in headers]
    entries += [(header, group) for group, headers in vocab.VAGUE for header in headers]
    entries += [(header, UNMAPPED_ONLY) for headers in vocab.NOISE_HEADERS.values() for header in headers]
    for header, meaning in entries:
        key = generator.normalized(header)
        assert meanings.setdefault(key, meaning) == meaning, header


def test_every_target_field_has_many_names() -> None:
    assert set(vocab.CLEAR) == set(generator.TARGETS)
    assert min(len(headers) for headers in vocab.CLEAR.values()) >= 10
    assert all(any(field in group for group, _ in vocab.VAGUE) for field in generator.TARGETS)


def test_the_careful_reading() -> None:
    email = frozenset({Field.EMAIL})
    assert careful_reading(email, value_fits("email")) == email
    assert careful_reading(EVERY, value_fits("email")) == email  # an opaque header: the values decide
    assert careful_reading(UNMAPPED_ONLY, value_fits("last_login")) == UNMAPPED_ONLY  # a decoy named as one
    assert careful_reading(EVERY, value_fits("last_login")) == frozenset({Field.SIGNUP_DATE})  # undecidable
    assert careful_reading(EVERY, value_fits("flag")) == UNMAPPED_ONLY


def test_decoys_always_name_what_they_are() -> None:
    for column in every_column():
        if column.kind in generator.LOOKS_LIKE:
            assert column.header_class == "clear" and column.header_fits == UNMAPPED_ONLY, column


def test_the_header_alone_often_does_not_decide() -> None:
    classes = Counter(column.header_class for column in every_column())
    total = sum(classes.values())
    assert classes["opaque"] / total > 0.1 and classes["vague"] / total > 0.15
    cases_with_a_header_that_does_not_decide = sum(
        any(column.header_class != "clear" for column in generator.case(case).columns) for case in ALL
    )
    assert cases_with_a_header_that_does_not_decide > 0.95 * generator.CASES


def test_the_two_dates_and_the_numbers_are_told_apart_by_their_values() -> None:
    years = {Field.BIRTH_DATE: set(), Field.SIGNUP_DATE: set()}
    lengths = {Field.CUSTOMER_ID: set(), Field.POSTAL_CODE: set()}
    for column in every_column():
        if column.target in years:
            years[column.target] |= {int(part) for part in re.findall(r"\d{4}", " ".join(column.samples))}
        if column.target in lengths:
            lengths[column.target] |= {len(value) for value in column.samples}
    assert max(years[Field.BIRTH_DATE]) <= 2005 and min(years[Field.SIGNUP_DATE]) >= 2015
    assert lengths[Field.CUSTOMER_ID].isdisjoint(lengths[Field.POSTAL_CODE])


def test_positions_and_opaque_headers_say_nothing_about_the_field() -> None:
    by_slot = Counter()
    opaque_templates = {field: set() for field in Field}
    for case in ALL:
        for index, column in enumerate(generator.case(case).columns):
            by_slot[(index, column.target is Field.UNMAPPED)] += 1
            if column.header_class == "opaque":
                opaque_templates[column.target].add(re.sub(r"\d+", "#", column.header))
    unmapped_share = [by_slot[(index, True)] / generator.CASES for index in range(10)]
    assert max(unmapped_share) - min(unmapped_share) < 0.08
    seen = [templates for templates in opaque_templates.values() if templates]
    assert all(len(templates) >= 8 for templates in seen)
