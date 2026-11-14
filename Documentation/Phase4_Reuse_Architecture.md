# Phase 4 — Reuse and Domain Engineering

## Commonality

Both a library and an equipment desk lend a named item to an active member. Both need catalogue search, a quantity of available copies, open-loan records, due dates, a member limit, return processing, and an atomic stock/loan update. The rules must be evaluated within a transaction so an unsuccessful operation does not leave only half of its state changes committed [1], [2].

## Variability

| Feature | Library book | Equipment |
|---|---|---|
| Descriptive fields | Title and author | Item name and optional owner/department description |
| Item identifier | Catalogue ID | Equipment ID; a composite type + ID allows the same numeric value in both domains |
| Loan policy | The supplied rules: three open books, fourteen days, one unspecified unit per completed overdue day | University rules were not supplied; the example configuration is labeled as demonstration data and can be changed by item type |
| Search | Title and author | Item name and descriptive field |
| Potential future fields | ISBN, edition | Asset tag, condition, maintenance status, calibration date |

The equipment-specific examples do not assert real campus inventory or policy. The handout names laptops, projectors, cameras, and laboratory instruments but gives no quantities, fine rate, or loan period for them [1].

## Proposed reusable domain architecture

The system uses a shared `BorrowableItem` record with an `ItemType` (`BOOK` or `EQUIPMENT`), an ID, a name, an optional descriptive field, and total/available copy counts. A `Loan` points to the item by `(item_type, item_id)`. `LendingService` applies the same borrow/return flow to either kind, while a policy map supplies the limits and dates for each type. The active book policy remains three books and fourteen days; the sample equipment policy is explicitly illustrative.

The console is a delivery mechanism, not the source of the lending rules. `Storage` is the application-facing port; `SQLiteRepository` and `DuckDBRepository` select the database at startup. Both use named domain records, and the storage adapter owns query details and transactions. The final shared physical schema stores resources in `items` and distinguishes them by `item_type`; migration maps the legacy `books` rows into `items` while preserving member, loan, date, and ID values. The SQL repository is shared because the tested operations use SQL understood by both supported engines; the engine-specific connection and transaction policy remain in separate adapters [8], [10].

```text
Console CLI
    ↓
LendingService ── LoanPolicy by item type
    ↓
Storage port ───── named Member / BorrowableItem / Loan records
    ↓
SQLiteRepository  |  DuckDBRepository
    ↓                         ↓
SQLite database       DuckDB database
```

The implementation intentionally does not add maintenance scheduling, equipment condition tracking, ISBNs, barcodes, reservations, or fine payment. Those are possible variable features, but the handout does not require them. If required later, they can be added to an equipment profile without duplicating the common circulation flow.

## Implementation evidence

The same `LendingService` and table structure borrow and return both item types. An automated test runs the example book and equipment policies on SQLite and DuckDB, checks their different due dates/limits, and verifies that a book loan does not consume the equipment-only limit. Demo records are created only in a fresh local database; the README labels their copy counts as examples, not verified university inventory.

## References

[1] Department of Computer Science, “SE431 Software Maintenance and Evolution Fall 2026 Project Description,” course handout, 2026, p. 2.

[2] “Legacy Library System — ~100 LOC,” supplied project source, 2026.

[8] SQLite, “Transaction,” *SQLite Documentation*. https://www.sqlite.org/lang_transaction.html

[10] DuckDB, “Python DB API,” *DuckDB Documentation*. https://duckdb.org/docs/api/python/dbapi
