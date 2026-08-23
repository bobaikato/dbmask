# Getting started

## Install

```bash
pip install dbmask                    # core (SQLite works out of the box)

pip install "dbmask[postgres]"        # psycopg2 driver
pip install "dbmask[mysql]"           # PyMySQL
pip install "dbmask[mssql]"           # pyodbc
pip install "dbmask[oracle]"          # oracledb
pip install "dbmask[databases]"       # all of the above

pip install "dbmask[openai]"          # OpenAI / OpenAI-compatible LLM fallback
pip install "dbmask[local]"           # local HTTP models (Ollama, LM Studio)
pip install "dbmask[all]"             # everything
```

Python 3.9–3.14. (3.9 is tested for compatibility but is past its CPython
end-of-life; plan to move on.)

## The five-minute loop

Everything runs locally against a throwaway SQLite file first — the workflow
is identical for a real database, only the URL changes.

### 0. A demo database

```bash
python -c "
import sqlite3
db = sqlite3.connect('demo.db')
db.executescript('''
CREATE TABLE customers (id INTEGER PRIMARY KEY, full_name TEXT, email TEXT);
INSERT INTO customers (full_name, email) VALUES
  ('Mary Johnson', 'mary.johnson@corp.example'),
  ('Robert Smith', 'robert.smith@corp.example'),
  ('Linda Davis',  'linda.davis@corp.example');
'''); db.commit()"
```

### 1. A minimal config

```yaml
# dbmask.yaml
database:
  url: sqlite:///demo.db
source_database:
  url: sqlite:///demo_original.db   # untouched copy, used by `validate`
detection:
  skip_column_patterns: ["^id$"]    # surrogate keys aren't sensitive
masking:
  seed: pick-a-private-seed
```

For a real database, point `database.url` at the **copy** you want to mask
(never production itself) and use `${ENV_VAR}` placeholders for credentials —
see [Configuration](configuration.md).

### 2. Scan — read-only

```text
$ dbmask scan --config dbmask.yaml
[ok       ] main.customers.id (skip, conf=1.00)
[SENSITIVE] main.customers.full_name -> full_name (pattern, conf=0.90)
[SENSITIVE] main.customers.email -> email (pattern, conf=1.00)

--- Summary ---
Columns analyzed : 3
Sensitive found  : 2
Needs review     : 0 (unknown)
```

Columns reported `UNKNOWN ?` could not be classified. They will **not** be
masked — decide them in the [overrides file](configuration.md#field-overrides)
or enable the [LLM fallback](llm.md).

### 3. Preview — dry run, redacted

```text
$ dbmask mask --config dbmask.yaml
=== Masking DRY-RUN (no changes written) ===

main.customers  (scanned=3, written=0)
  - full_name: rule=full_name -> strategy=fake_name
  - email: rule=email -> strategy=fake_email
    before: {'full_name': '**** *******', 'email': '****.*******@****.*******'}
    after : {'full_name': 'Stephanie Davis', 'email': 'karen.lopez316@example.invalid'}
```

Originals are shown shape-redacted so nothing sensitive lands in scrollback
or CI logs (`--show-values` reveals them). A dry run has **no side effects**
— it does not even record seed-map pairs.

### 4. Apply

```bash
cp demo.db demo_original.db      # keep the original for validation
dbmask mask --config dbmask.yaml --apply
```

Without `--apply`, `mask` never writes — no config option can change that.

### 5. Validate — prove it worked

```text
$ dbmask validate --config dbmask.yaml --strict
[✓] row_count              main.customers: Row counts match (3).
[✓] schema_elements        main.customers: columns/types match.
...
[✓] masking_completeness   main.customers.email: PK-aligned comparison of 3 row(s): every sensitive value differs from its source.

RESULT: PASSED ✓
```

`validate` exits non-zero on failure, so it slots straight into a CI gate.
`--strict` also fails on anything that could not be verified — see
[Validation](validation.md).

## Using it as a library

```python
from dbmask.config import Config
from dbmask.runner import Runner

config = Config.load("dbmask.yaml")
config.masking.dry_run = False

with Runner(config) as runner:
    report = runner.scan()
    for d in report.unknown:
        print("review me:", d.schema, d.table, d.column)
    results = runner.mask(report.decisions)
    validation = runner.validate()
    assert validation.passed_strict
```

[`examples/quickstart.py`](https://github.com/sealandseacat/dbmask/blob/main/examples/quickstart.py)
is a runnable end-to-end version of this.

!!! warning "The three safety rules"
    1. Mask a **copy**, never production.
    2. Review `UNKNOWN` columns — they are *not* masked.
    3. Gate downstream use on `validate --strict`.
