"""Answers that do not read the export the way a careful person does, and the key itself, as mappings
{slot value: field value}. tests/test_baselines.py scores them; the milestone's evidence script reuses them."""

from __future__ import annotations

import random
import re

from contract import Field, Slot

SLOTS = [slot.value for slot in Slot]
FIELDS = [field.value for field in Field]


def all_unmapped(export: dict) -> dict[str, str]:
    return {slot: Field.UNMAPPED.value for slot in SLOTS}


def constant(field: Field):
    return lambda export: {slot: field.value for slot in SLOTS}


def random_fields(rng: random.Random):
    return lambda export: {slot: rng.choice(FIELDS) for slot in SLOTS}


def oracle(key: dict) -> dict[str, str]:
    return {entry["slot"]: entry["target"] for entry in key["keys"]}


# The naive mapper: an exact lookup of the header, ignoring case, spaces and punctuation, in a small
# dictionary of the obvious English names; anything else is left unmapped. It never reads a value.
OBVIOUS = {
    "id": "customer_id",
    "customerid": "customer_id",
    "name": "full_name",
    "fullname": "full_name",
    "firstname": "first_name",
    "lastname": "last_name",
    "email": "email",
    "phone": "phone",
    "dob": "birth_date",
    "birthdate": "birth_date",
    "dateofbirth": "birth_date",
    "street": "street",
    "address": "street",
    "city": "city",
    "state": "state",
    "zip": "postal_code",
    "zipcode": "postal_code",
    "postalcode": "postal_code",
    "country": "country",
    "signupdate": "signup_date",
    "ltv": "lifetime_value",
    "lifetimevalue": "lifetime_value",
}


def header_only(export: dict) -> dict[str, str]:
    out = {}
    for column in export["columns"]:
        key = re.sub(r"[\W_]+", "", column["header"].lower())
        out[column["slot"]] = OBVIOUS.get(key, Field.UNMAPPED.value)
    return out


# The pattern mapper: regular expressions on the sample values only, never the header; a field already
# taken leaves the next column unmapped. It cannot tell names, cities and countries apart, and it maps every
# decoy whose values look like a field's.
YEAR = re.compile(r"(?<!\d)(19\d\d|20\d\d)(?!\d)")
DATE = re.compile(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}|[A-Z][a-z]{2} \d{1,2}, \d{4}|\d{2}-[A-Z][a-z]{2}-\d{4}")
MONEY = re.compile(r"^(\$|EUR )?[\d.,]+[.,]\d\d( USD| €)?$")


def guess(samples: list[str]) -> str:
    if all("@" in value for value in samples):
        return "email"
    if all(DATE.search(value) for value in samples):
        years = [int(YEAR.search(value).group(1)) for value in samples if YEAR.search(value)]
        if years and max(years) <= 2005:
            return "birth_date"
        if years and min(years) >= 2015:
            return "signup_date"
        return "unmapped"
    if all(re.fullmatch(r"\d{5}(-\d{4})?", value) for value in samples):
        return "postal_code"
    if all(re.fullmatch(r"\d{7,9}", value) for value in samples):
        return "customer_id"
    if all(re.fullmatch(r"[+(]?[\d][\d ().-]{7,}\d", value) for value in samples):
        return "phone"
    if all(MONEY.match(value) for value in samples):
        return "lifetime_value"
    if all(re.fullmatch(r"[A-Z]{2}", value) for value in samples):
        return "state"
    if all(re.search(r"\d", value) and re.search(r"[A-Za-z]{3,}", value) and " " in value for value in samples):
        return "street"
    return "unmapped"


def value_patterns(export: dict) -> dict[str, str]:
    out, taken = {}, set()
    for column in export["columns"]:
        field = guess(column["samples"])
        if field != "unmapped" and field in taken:
            field = "unmapped"
        taken.add(field)
        out[column["slot"]] = field
    return out
