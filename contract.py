"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    PIN_MAPPING = "pin_mapping"
    READ_EXPORT = "read_export"


class Task(Enum):
    MAP_COLUMNS = "map-columns"


class Slot(Enum):
    COL01 = "col01"
    COL02 = "col02"
    COL03 = "col03"
    COL04 = "col04"
    COL05 = "col05"
    COL06 = "col06"
    COL07 = "col07"
    COL08 = "col08"
    COL09 = "col09"
    COL10 = "col10"


class Field(Enum):
    CUSTOMER_ID = "customer_id"
    FULL_NAME = "full_name"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    PHONE = "phone"
    BIRTH_DATE = "birth_date"
    STREET = "street"
    CITY = "city"
    STATE = "state"
    POSTAL_CODE = "postal_code"
    COUNTRY = "country"
    SIGNUP_DATE = "signup_date"
    LIFETIME_VALUE = "lifetime_value"
    UNMAPPED = "unmapped"


CASE = "Which customer export to map, from 0 to 999; every case is fixed"
SLOT = "The column's place in the export, col01 to col10"


@dataclass
class CaseInput(Output):
    case: Annotated[int, CASE]


@dataclass
class Profile(Output):
    shapes: Annotated[
        list[str],
        "Each distinct sample's character pattern, in sample order: 9 per digit, A for a run of letters that starts "
        "upper case, a for one that starts lower case; other characters kept",
    ]
    length: Annotated[str, "The fewest and the most characters among the samples, as min-max"]
    digit_share: Annotated[float, "Share of the samples' characters that are digits, 0 to 1, 2 decimals"]


@dataclass
class Column(Output):
    slot: Annotated[Slot, SLOT]
    header: Annotated[str, "The column's header, as the source system named it"]
    samples: Annotated[list[str], "Four values from the column, as exported"]
    profile: Annotated[Profile, "Facts computed from the samples by a fixed rule: hints, not answers"]


@dataclass
class ExportOutput(Output):
    case: Annotated[int, "The case number, as asked"]
    columns: Annotated[list[Column], "The export's 10 columns, in slot order"]


@dataclass
class Key(Output):
    slot: Annotated[Slot, SLOT]
    target: Annotated[Field, "The target field the column holds, or unmapped when it fits none"]


@dataclass
class PinOutput(Output):
    case: Annotated[int, "The case number, as asked"]
    generator: Annotated[str, "Name and version of the generator that made the case"]
    keys: Annotated[list[Key], "The case's answer key, one entry per slot, in slot order"]


COLUMN = "The target field this column holds, or unmapped when it fits none"


@dataclass
class MappingOutput(Output):
    case: Annotated[int, "The case number, as given"]
    col01: Annotated[Field, COLUMN]
    col02: Annotated[Field, COLUMN]
    col03: Annotated[Field, COLUMN]
    col04: Annotated[Field, COLUMN]
    col05: Annotated[Field, COLUMN]
    col06: Annotated[Field, COLUMN]
    col07: Annotated[Field, COLUMN]
    col08: Annotated[Field, COLUMN]
    col09: Annotated[Field, COLUMN]
    col10: Annotated[Field, COLUMN]


TOOLS = {
    Tool.PIN_MAPPING: (CaseInput, PinOutput),
    Tool.READ_EXPORT: (CaseInput, ExportOutput),
}
TASKS = {Task.MAP_COLUMNS: (CaseInput, MappingOutput)}
