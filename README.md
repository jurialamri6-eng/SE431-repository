# SE431 Library System

## Team

| Student | University ID | Assigned share of final review |
| --- | --- | --- |
| Nada Faisal | 4320021 | 50% |
| Juri Alamri | 4311905 | 50% |

Appendix C of the report lists six paired review tasks, with one responsibility for each student in every pair.

## Setup

Use Python 3.11 or newer. Open PowerShell in the extracted project folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Source_Code\dev-requirements.txt
Set-Location Source_Code
```

This installs DuckDB and the Radon measurement tool. SQLite is included with Python. The following commands assume that the current folder is `Source_Code`.

## Run the book system

```powershell
..\.venv\Scripts\python.exe -m library_system --engine sqlite --database ..\runtime\library.sqlite3
```

For DuckDB, use a separate database file:

```powershell
..\.venv\Scripts\python.exe -m library_system --engine duckdb --database ..\runtime\library.duckdb
```

The menu has search, borrow, return and exit options. An empty database receives sample data. Try member `S1` and book `1`, Clean Code. When a member has two open loans for the same title, select the loan ID to return the correct loan.

Add `--item-type equipment` to either command to use the equipment example. Its inventory and policy values are demonstration settings.

## Tests and measurements

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
..\.venv\Scripts\python.exe tools\quality_metrics.py
```

The supplied source passes 33 tests. SQLite and DuckDB keep the same accented-search behavior. A successful return reports `returned=True`, and a repeated return leaves stock unchanged.

The final source measures 888 physical lines and 598 logical lines, with 74 functions and 12 classes. The complexity of `borrow()` is 5. The measurement script excludes test code and writes `Evidence/quality_metrics.json` in the project folder.

`Evidence/test-results.txt`, `Evidence/quality_metrics.json` and `Evidence/correction-checks.txt` contain the current verification results. To save a new test log:

```powershell
New-Item -ItemType Directory -Force ..\Evidence | Out-Null
..\.venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1 | Tee-Object -FilePath ..\Evidence\test-results.txt
```

## Migration

Migration reads a separate legacy SQLite database and writes to an empty destination without changing the source. It preserves IDs and dates and checks record counts and stock. Tests use sample databases based on the original schema.

The old availability flag does not show the number of purchased copies. Supply checked `book_id,total_copies` values when needed. The following example uses source files that you supply in `incoming/`:

```powershell
New-Item -ItemType Directory -Force ..\runtime | Out-Null
..\.venv\Scripts\python.exe -m library_system.migration ..\incoming\legacy.sqlite ..\runtime\migrated.duckdb --engine duckdb --inventory-csv ..\incoming\verified_inventory.csv
```

## Contents

- `Source_Code/`: application, policy settings, tests, the original source, runnable legacy copy, maintenance baseline and measurement tool.
- `Demo/SE431_Demo.mp4`: terminal demonstration.
- `Drawio_Diagrams/`: editable diagram source and four PNG diagrams.
- `Evidence/`: current tests, measurements and regression checks.

https://github.com/jurialamri6-eng/SE431-repository/
