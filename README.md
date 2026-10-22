# Schema Mapper

A `nanoagent.plugin/v0001` plugin. A model reads a messy customer export of ten
columns, each a header and four sample values, and decides which field of one
target schema each column holds, or that it fits none. A deterministic verifier
grades the mapping against the answer key of the seeded generator that made the
export, which the model never sees.

## Tools

| Tool | Does | Code |
|---|---|---|
| `read_export` | Shows a case's 10 columns: each one's header, four sample values, and facts computed from the samples by a fixed rule (character patterns, length range, share of digits) | `src/plugin/export.py` |
| `pin_mapping` | Makes the case's answer key with the pinned generator: the true field of every column; the task's reference, run out of the model's sight | `src/plugin/export.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `map-columns` | Decides which target field each of an export's 10 columns holds | `decide`, with `read_export`; reference `pin_mapping` |

The input is a case number from 0 to 999. The output is the case number and one
field per column, `col01` to `col10`, each one of `customer_id`, `full_name`,
`first_name`, `last_name`, `email`, `phone`, `birth_date`, `street`, `city`,
`state`, `postal_code`, `country`, `signup_date`, `lifetime_value` or
`unmapped`. With the `decide` runner the model writes no value of its own: it
chooses the next step and the ten fields (all ten in one request), and NanoAgent
copies the case number, so a whole run takes three requests.

### Data

Every export is made by `src/plugin/generator.py` (version
`schema-mapper-gen/1`) from a stream of SHA-256 blocks seeded with
SHA-256(`schema-mapper:<case>`), so the same number gives the same export on
every machine. Nothing is downloaded and no real person's data is used: names,
streets and companies are drawn from short made-up lists, e-mail addresses use
the reserved `example` domains and US phone numbers the fictional 555-01xx range.

A case holds 7 to 9 columns of distinct target fields and 1 to 3 columns that fit
none, shuffled. The header alone does not decide a column:

- Headers come from 216 names of the 14 fields (11 to 22 each), abbreviated, in English,
  German, Spanish or French, or as vendor systems name them (`KUNNR`, `TELF1`,
  `MailingCity`, `Account_Number__c`), in mixed case styles.
- About one header in five is vague, naming a group the samples must settle
  (`Name`, `Datum`, `Nr.`, `Code`, `Adresse`, `St`), and about one in seven is
  opaque (`fld_07`, `attr2`, `Spalte12`).
- The samples settle what the header leaves open: birth dates (1940 to 2005)
  against signup dates (2015 to 2026) in up to seven date formats; customer numbers
  (7 to 9 digits) against postal codes (5 digits or ZIP+4) against phone numbers
  (always written with separators); full names against given names against
  surnames; state codes and names against countries.
- Columns that fit no field are flags, category codes, free-text notes, company
  names, and decoys whose values look like a field's: a last-login date, a credit
  limit or open balance, a sales rep's name, loyalty points, order counts,
  internal reference and promo codes.

Each case is checked as it is made, so that one answer is right and a careful
reader can reach it (`careful_reading` in `generator.py`): a column whose header
names something that is not a target field, or whose values fit no field, is
unmapped; any other column is the one field its header and its values both
allow. A decoy therefore always has a header that says what it is, an opaque
header only sits on a column whose values decide it, given names, surnames,
cities, states and countries never share a word, and no case uses a field twice.
`tests/test_generator.py` checks this for all 1,000 cases.

### What the verifier checks

`verifier/mapping.py` checks, in order; any failure among the first six scores 0:

| Id | Constraint |
|---|---|
| `key-case` | The answer key is for the task's case |
| `key-generator` | The answer key comes from the pinned generator version |
| `key-slots` | The answer key has one entry per slot, col01 to col10, in order |
| `key-fields` | The answer key uses every target field at most once |
| `key-unmapped` | The answer key leaves 1 to 3 columns unmapped |
| `same-case` | The output answers the task's case |
| `columns-right` | Every column is mapped to the field it holds, or unmapped when it fits none |
| `field-once` | No field is used for two columns |
| `unmapped-kept` | No column that fits no field is put on a field |

The verdict is valid only when all ten columns are right. The score is chance
corrected against the best answer that reads nothing, every column unmapped,
which gets the case's *u* unmapped columns right; a column put on a wrong field
costs half a column more, because in an import a wrong field silently fills the
target with another column's data, while an unmapped column is left for review:

    score = max(0, (right - wrong_field / 2 - u) / (10 - u))

So every column unmapped, any one field for every column, and random fields all
score 0, and the answer key scores 1. Plain accuracy would give "every column
unmapped" 0.1 to 0.3 and would not charge anything for guessing. Forcing an
unmappable column onto a field, or using a field twice, always puts a column on
a wrong field, so both rules cost through the same term and are reported as
their own constraints.

Over all 1,000 cases, a header lookup in a small dictionary of the obvious
English names (`tests/agents.py`) scores 0.08 on average and maps no case fully
right; regular expressions on the sample values score 0.56 and map 4 cases fully
right, because they cannot tell names from cities or countries, and they take
every decoy for the field it imitates. `tests/test_baselines.py` checks these
bounds, and the trivial answers, on 200 cases.

The tool checks (`verifier/export.py`, `verifier/pin.py`) refuse a case number
out of range, a shown export that is not exactly col01 to col10 in order, a
blank or repeated header, a column without four non-blank samples, profile
hints that do not match the samples, and an answer key that breaks any of the
key constraints above.

### Limits

- The exports are synthetic. Real exports hold blanks, mixed formats within a
  column and headers that contradict their values; these do not, so that every
  case has exactly one right answer.
- Telling given names from surnames, or cities from streets, relies on the
  reader knowing common European and American names; four samples per column
  make this easy for a careful person but not for a rule.
- A rule written with the generator's own word lists could map every case; the
  task measures reading with general knowledge, not with those lists.

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions (no network), tools, the map-columns task
├── contract.py      # typed inputs and outputs: CaseInput, ExportOutput, PinOutput, MappingOutput, Field
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # empty: the plugin needs no environment variables
├── src/plugin/      # the MCP server (__main__.py), the tools (export.py), the generator and its word lists
├── tests/           # oracle, wrong, tampered and trivial answers; the generator's promises over all cases
├── ui/              # outputs are drawn from their JSON Schema
├── product/         # the product page: product.yaml and icon.svg
└── verifier/        # deterministic checks: mapping.py (the task), export.py and pin.py (the tools), rules.py
```

`verifier/rules.py` restates the plugin's fixed rules (the generator version,
the number of cases and samples, and the profile hints) because the verifier
may not import the plugin's own code; `tests/test_rules.py` checks that both
copies agree.

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

Publishing checks every plugin rule: push the plugin to a public GitHub
repository and submit its URL on RUSH Lab's Marketplace.
