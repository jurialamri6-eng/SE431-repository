# SE431 Legacy Library Reengineering

This repository contains the SE431 Fall 2026 library system analysis, maintenance implementation, refactoring, reuse design, quality measurements, and delivery artifacts.

This is the 22 November review copy. Team details, contribution records, the shared repository link and Teams submission are awaiting team input.

## What is implemented

- **MR-01:** copy counts, atomic borrowing and returns, and loan-ID selection when the same member has multiple loans for a title.
- **MR-02:** SQLite remains supported; DuckDB is a real alternate backend. A setting selects the engine, and a one-way importer preserves legacy IDs and dates while checking migrated data.
- **Phase 3:** `LendingService` holds the lending rules, the console stays in `cli.py`, and repository rows map to named records. The default book menu matches the post-maintenance book workflow on both engines.
- **Phase 4:** book and equipment borrowing share the same item, loan, policy, service, and storage contracts. Equipment policy and inventory examples are explicitly labeled demo values.
- **Phase 5:** `Source_Code/tools/quality_metrics.py` measures the normalized legacy executable and production package with Radon 6.0.1 and Python AST. The output is `Evidence/quality_metrics.json`.
- **Review fixes:** searches on both engines follow the original SQLite matching rules. A successful return supplies a loan record marked returned, matching the stored row.

## Requirements

- Python 3.11 or newer.
- SQLite ships with Python. DuckDB is pinned in `Source_Code/requirements.txt`.

From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Source_Code\requirements.txt
Set-Location Source_Code
..\.venv\Scripts\python.exe -m library_system --engine sqlite --database ..\runtime\library.sqlite3
```

Choose menu options 1 to search, 2 to borrow, 3 to return and 4 to exit. Try Clean Code (book ID `1`) as member `S1` in the sample data.

Use `--engine duckdb` and a separate `.duckdb` path for DuckDB. Add `--item-type equipment` to switch to the equipment menu. On an empty database the CLI loads demonstration members, books and equipment.

## Tests and measurements

For tests, measurements and document rebuilds, install the development requirements into the same environment. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r Source_Code\dev-requirements.txt
```

Run the direct checks from the repository root:

```powershell
.\.venv\Scripts\python.exe Demo\demo_regressions.py
```

From the repository root, enter `Source_Code` and run the suite and metrics:

```powershell
Set-Location Source_Code
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
..\.venv\Scripts\python.exe tools\quality_metrics.py
```

The development file includes the runtime requirements and Radon. The suite covers both engines, concurrency, search, fines, dates, rollback, equipment and migration. It checks accented search against the original SQLite behavior and compares the returned loan with its stored state. The original source text is preserved alongside the separate syntax repair.

## Legacy migration

The migration accepts a separate source SQLite database and destination. It never overwrites the source. Because the legacy `available` flag does not reveal purchased copy quantities, provide verified `book_id,total_copies` values when a title has more than one copy. Example:

```powershell
..\.venv\Scripts\python.exe -m library_system.migration ..\incoming\legacy.sqlite ..\runtime\migrated.duckdb --engine duckdb --inventory-csv ..\incoming\verified_inventory.csv
```

No original legacy database was included with the supplied source code, so migration tests use generated fixtures following the documented legacy schema. The migration's behavior against a real university database has not been claimed.

## Project artifacts

- `Documentation/` — Phase 1–2 analysis and Phase 4 design.
- `Report/` — final editable Word report with an automatic table of contents, refreshed PDF, and the University of Prince Mugrin logo.
- `Presentation/` — editable student presentation based on the official UPM PowerPoint template.
- `Demo/` — screen recording of the live terminal, guide and transcripts for both engines.
- `Drawio_Diagrams/` — editable diagrams.net source, four project diagrams on Pages 3–6, the supplied pages and a vector PDF for reading.
- `Evidence/` — assignment text extraction, test output, and quality metrics.
- `Git/` — cloneable local bundle with the six original stages and the two review commits.
- `Final_Checklist.md` — requirements-to-evidence checklist, including pending team details.
- `Documentation/review_status.json` — confirmed project dates and the shared team, task and collaboration fields used to build the report and slides.

To rebuild the report, run `..\.venv\Scripts\python.exe build_report.py` from `Report`, then run `..\.venv\Scripts\python.exe refresh_docx_fields.py`. This refreshes the automatic contents and page fields with installed Microsoft Word, saves the DOCX, and exports the matching PDF with LibreOffice.

## Before submission

The shared repository link has not been supplied. The local history can be cloned with `git clone Git/SE431-project.bundle SE431-history`. The earlier commit authorship is retained, including Codex-assisted work.

Enter the team number, 3–4 member names and IDs, instructor name and genuine contribution records. Confirm that the instructor can open the repository link. Rename the ZIP using the team number and submit to Microsoft Teams by 22 November 2026 at 11:59 PM. See `Final_Checklist.md` for the complete review.
