# SE431 — Program Comprehension and Maintenance Design

**Status:** Analysis of the supplied legacy source; MR-01/MR-02 sections are proposed designs until implementation and evidence are added.

## Scope and method

The supplied `Legacy Library System — ~100 LOC.txt` was reviewed without changing it. The analysis follows function calls, SQL statements, state updates, and the six requirements in the Fall 2026 project description [1], [2]. The text file has lost indentation inside function bodies, and its final entry guard is `if name == "main"`; as supplied, it cannot be executed as Python. The behavioural description below is therefore based on static inspection, not a runtime test. The original is retained under `Source_Code/legacy/`.

## Phase 1: program comprehension

### Requirements and business rules

| Requirement | Evidence in the legacy source | Finding |
|---|---|---|
| Active members may borrow | `borrow()` reads `members.status` | Enforced when the value is exactly `ACTIVE`; there is no authentication. |
| A member may have at most three books | `borrow()` counts loans with `returned=0` | Enforced for all outstanding loan rows. |
| Borrow only available books | `borrow()` reads and updates `books.available` | One Boolean-style availability flag supports one copy per title. |
| Normal loan period is 14 days | `borrow()` adds `timedelta(days=14)` | Due time is the current time plus fourteen days. |
| Late returns incur a fine | `return_book()` computes `(today - due).days` | It prints one unspecified unit per completed overdue day; it does not persist a debt or payment. One hour late yields 0; 25 hours late yields 1. |
| Members can search books | `search_books()` queries title and author | Results include unavailable books. `%` and `_` entered by a user retain SQL wildcard meaning. Empty text matches all seeded books. |

Borrow checks run in this order: member exists, member is active, book exists, book is available, then the member is below the three-loan limit. A rejection prints a message and returns `False` before writes. There is no rule for overdue loans or unpaid fines. A return must match an outstanding loan for the member and book; it marks the loan returned and sets the book available. Repeated borrowing of the same title is not possible in the intended single-copy design [2].

### Current architecture and data flow

The system is one procedural Python script with five functions and no classes. `main()` collects console input and passes one open SQLite connection to the other functions. `setup()` creates and seeds the schema; search reads and prints rows; borrow checks policy, writes the loan and availability flag, commits, and prints the due date; return calculates a fine, closes the loan, restores availability, and commits. The original Drive diagram is retained in `Project_References/library.drawio`.

### Function responsibilities

| Function | Responsibility | Direct dependencies |
|---|---|---|
| `setup()` | Open connection; create schema; seed demonstration records. | `sqlite3`, file path, all tables. |
| `search_books()` | Search titles/authors, print availability, return tuples. | SQL/cursor, `books`, console output. |
| `borrow()` | Check eligibility, calculate dates, insert loan, change stock. | `members`, `books`, `loans`, `datetime`, console output. |
| `return_book()` | Find active loan, calculate fine, close it, restore stock. | `loans`, `books`, `datetime`, console output. |
| `main()` | Menu, parse input, dispatch operations, close on normal exit. | All four functions, `input()`, `print()`. |

`setup()`, search, borrow, and return all issue SQL directly. This spreads database decisions through the script. Passing a connection is a small separation, but does not hide SQL, cursors, or positional tuples.

### Database structure

| Table | Declared columns | Meaning and limits |
|---|---|---|
| `members` | `id TEXT PRIMARY KEY`, `name TEXT`, `status TEXT` | Member identity/status; no declared status constraint. |
| `books` | `id INTEGER PRIMARY KEY`, `title`, `author`, `available INTEGER` | One catalogue row and one availability flag; no copy quantity. |
| `loans` | `id INTEGER PRIMARY KEY AUTOINCREMENT`, `member_id`, `book_id`, `borrow_date`, `due_date`, `returned` | Loan history; relationships are logical only because the DDL declares no foreign keys. |

Dates are ISO-formatted text. There are no explicit `NOT NULL`/`CHECK` constraints, copy identifiers, return timestamps, or persisted fines. The application keeps book availability and open loans in sync, but the database does not enforce that agreement. `setup()` seeds two active members and three books with `INSERT OR IGNORE` [2].

### Code smells and risks

| Finding | Evidence | Maintenance impact |
|---|---|---|
| Long method | `borrow()` handles eligibility, dates, SQL, state changes, and messages. | A policy edit requires reasoning across unrelated work. |
| Mixed responsibilities | Search/borrow/return combine data access with console output. | Business behaviour is difficult to test independently. |
| Scattered persistence | Four functions know about SQLite details. | Replacing the engine changes multiple functions. |
| Magic policy values | `3`, `14`, `ACTIVE`, and `0/1` are embedded. | Policy meaning is not centralized. |
| Positional data | `member[1]`, `book[0]`, and `loan[1]`. | Column-order changes can silently alter meaning. |
| Duplicated state | `books.available` overlaps with outstanding loan state. | A partial write can make the two representations disagree. |

Other concerns include unhandled input/date/database errors, no explicit rollback path, and a read-check-write sequence that can race between separate clients. These are static observations, not test findings [2], [5].

## Phase 2: maintenance design

### MR-01 — Multiple copies

**Classification:** perfective maintenance in the traditional taxonomy; additive maintenance describes the new functionality in SWEBOK V4.0a [6], [7].

The current catalogue row records only whether a title is available. A quantity design replaces that Boolean with `total_copies` and `available_copies` (or equivalent fields), constrained by `0 <= available <= total`. Each open loan accounts for one copy; the member limit counts copies even when several loans refer to one title. Borrow must reserve one copy and insert one loan atomically. The return flow must select a specific loan when the same member has multiple open loans for a title; only the first transition from open to returned can restore one copy.

For legacy migration, a clean single-copy record can map to one total copy when its availability agrees with its open-loan count. An unavailable title with no open loan is ambiguous. Extra purchased quantities must come from verified inventory; they cannot be inferred from the Boolean flag. Preserve the source DB as a rollback copy and reconcile inconsistent rows before migration [8].

**Impact:** `setup()`/schema, catalogue search/display, borrowing, returning, menu input, and the books/loans tables. Members and the three-loan limit remain unchanged. Acceptance cases include exhausting two copies, restoring exactly one on return, a duplicate return, repeated-title loans, inactive members, member-limit rejection, transaction failure, and competing requests for the last copy.

### MR-02 — Replace the database implementation

**Classification:** adaptive maintenance: storage changes while required business behaviour stays the same [6].

Introduce a storage boundary that returns named records and owns SQL, value mapping, connection lifecycle, and transactions. Keep membership, loan limits, due dates, fines, and search semantics in the application/domain layer. Select one adapter at startup; do not dual-write. The complete read-check-update operation, including the member's active-loan count, belongs inside one transaction. Migration should pause writes, back up the source, preserve identifiers/dates/returned flags, validate row counts and references, and keep the old database available until the new one is accepted. Search matching and wildcard behaviour are part of the contract [2], [8], [9].

**Impact:** initialization/configuration, search, borrow, return, menu construction, and every table. Adapter acceptance checks run the same controlled searches, lending, returning, late-fine, limit, and failure scenarios against each engine, comparing returned data and resulting state.

## References

[1] Department of Computer Science, “SE431 Software Maintenance and Evolution Fall 2026 Project Description,” College of Computer and Cyber Sciences, course handout, 2026, pp. 1–3.

[2] “Legacy Library System — ~100 LOC,” supplied project source, 2026.

[3] E. J. Chikofsky and J. H. Cross II, “Reverse engineering and design recovery: A taxonomy,” *IEEE Software*, vol. 7, no. 1, pp. 13–17, Jan. 1990, doi: 10.1109/52.43044.

[4] Python Software Foundation, “datetime — Basic date and time types,” *Python 3 Documentation*. Available: https://docs.python.org/3/library/datetime.html

[5] M. Fowler, *Refactoring: Improving the Design of Existing Code*, 2nd ed. Addison-Wesley, 2018. Available: https://martinfowler.com/books/refactoring.html

[6] P. Bourque and R. E. Fairley, Eds., *Guide to the Software Engineering Body of Knowledge*, Version 3.0. IEEE Computer Society, 2014, ch. 5, sec. 1.6. Available: https://ieeecs-media.computer.org/media/education/swebok/swebok-v3.pdf

[7] H. Washizaki, Ed., *Guide to the Software Engineering Body of Knowledge*, Version 4.0a. IEEE Computer Society, Aug. 2026, ch. 7, sec. 1.6. Available: https://ieeecs-media.computer.org/media/education/swebok/swebok-v4.pdf

[8] SQLite, “Transaction,” *SQLite Documentation*. Available: https://www.sqlite.org/lang_transaction.html

[9] D. L. Parnas, “On the criteria to be used in decomposing systems into modules,” *Communications of the ACM*, vol. 15, no. 12, pp. 1053–1058, Dec. 1972, doi: 10.1145/361598.361623.
