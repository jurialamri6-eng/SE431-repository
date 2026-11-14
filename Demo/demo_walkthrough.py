"""Record real console sessions on fresh databases and save the transcripts."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source_Code"
DEMO = ROOT / "Demo"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

BOOK_SESSION = [
    ("Search for the title", ["1", "Clean Code"]),
    ("Borrow the first copy", ["2", "S1", "1"]),
    ("Borrow the second copy", ["2", "S1", "1"]),
    ("Reject the third request", ["2", "S1", "1"]),
    ("Return loan 1", ["3", "S1", "1", "1"]),
    ("Check the restored copy", ["1", "Clean Code"]),
]
EQUIPMENT_SESSION = [
    ("Search for the projector", ["1", "Projector"]),
    ("Borrow the projector", ["2", "S1", "2"]),
    ("Return the projector", ["3", "S1", "2", "1"]),
]


def read_prompt(stream, expected: str) -> str:
    chunks = []
    while True:
        char = stream.read(1)
        if not char:
            raise RuntimeError(f"Console exited before {expected!r}: {''.join(chunks)}")
        chunks.append(char)
        if char == expected[-1] and "".join(chunks).endswith(expected):
            return "".join(chunks)


def record_session(source: Path, args: list[str], groups: list, noun: str) -> dict:
    cmd = [sys.executable, "-u", "-m", *args]
    captures = []
    try:
        with subprocess.Popen(
            cmd, cwd=source, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", env=ENV,
        ) as process:
            pending = read_prompt(process.stdout, "Choice: ")
            for label, answers in groups:
                choice, *parameters = answers
                prompts = {
                    "1": ["Search: "],
                    "2": ["Member ID: ", f"{noun} ID: "],
                    "3": ["Member ID: ", f"{noun} ID: ", "Loan ID to return: "],
                }[choice][:len(parameters)]
                text = pending + choice + "\n"
                process.stdin.write(choice + "\n")
                process.stdin.flush()
                for prompt, answer in zip(prompts, parameters, strict=True):
                    text += read_prompt(process.stdout, prompt) + answer + "\n"
                    process.stdin.write(answer + "\n")
                    process.stdin.flush()
                pending = read_prompt(process.stdout, "Choice: ")
                output, menu = pending.rsplit("\nLIBRARY\n", 1)
                captures.append({"step": label, "text": text + output.rstrip() + "\n"})
                pending = "\nLIBRARY\n" + menu
            process.stdin.write("4\n")
            process.stdin.flush()
            process.stdin.close()
            ending = process.stdout.read()
            if process.wait(timeout=12) != 0:
                raise RuntimeError(ending or "Console returned a failing exit code.")
    except OSError as exc:
        raise RuntimeError(f"Unable to run the {noun.lower()} session.") from exc
    transcript = "".join(capture["text"] for capture in captures) + pending + "4\n" + ending
    return {"command": " ".join(["python", "-m", *args]), "captures": captures,
            "transcript": transcript, "exit_code": 0}


def run_migration(source: Path) -> dict:
    source_db = source / "library.db"
    before = sha256(source_db.read_bytes()).hexdigest()
    args = ["-m", "library_system.migration", "library.db", "../runtime/migrated.duckdb", "--engine", "duckdb"]
    result = subprocess.run(
        [sys.executable, *args], cwd=source, check=True, capture_output=True,
        encoding="utf-8", env=ENV, timeout=35,
    )
    after = sha256(source_db.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError("The legacy fixture changed during migration.")
    if not re.search(r"Migration complete: \{'members': 2, 'items': 3, 'loans': 1\}", result.stdout):
        raise RuntimeError(f"Unexpected migrated counts: {result.stdout}")
    return {"command": " ".join(["python", *args]), "transcript": result.stdout,
            "source_unchanged": before == after, "exit_code": 0}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="se431-demo-") as directory:
        checkout = Path(directory) / "Source_Code"
        shutil.copytree(SOURCE, checkout, ignore=shutil.ignore_patterns("__pycache__"))
        legacy = record_session(checkout, ["legacy.legacy_system_executable"], [
            ("Search the legacy catalog", ["1", "Clean Code"]),
            ("Create a legacy fixture loan", ["2", "S1", "1"]),
        ], "Book")
        sqlite = record_session(
            checkout, ["library_system", "--engine", "sqlite", "--database", "../runtime/demo.sqlite3"],
            BOOK_SESSION, "Book",
        )
        duckdb = record_session(
            checkout, ["library_system", "--engine", "duckdb", "--database", "../runtime/demo.duckdb"],
            BOOK_SESSION, "Book",
        )
        equipment = record_session(
            checkout, ["library_system", "--engine", "duckdb", "--database", "../runtime/equipment.duckdb",
                       "--item-type", "equipment"],
            EQUIPMENT_SESSION, "Equipment",
        )
        migration = run_migration(checkout)

    test_output = (ROOT / "Evidence" / "test-results.txt").read_text(encoding="utf-8")
    test_summary = re.search(r"Ran (\d+) tests in ([^\n]+)\n\nOK", test_output)
    if not test_summary:
        raise RuntimeError("No successful test run is recorded.")
    quality = json.loads((ROOT / "Evidence" / "quality_metrics.json").read_text(encoding="utf-8"))
    history = subprocess.run(
        ["git", "log", "--reverse", "--format=%s"],
        cwd=ROOT, check=True, capture_output=True, encoding="utf-8", timeout=15,
    ).stdout.strip()
    evidence = {
        "run_date": date.today().isoformat(),
        "sessions": {"legacy": legacy, "sqlite": sqlite, "duckdb": duckdb,
                     "equipment": equipment, "migration": migration},
        "test_count": int(test_summary.group(1)),
        "test_summary": test_summary.group(0),
        "quality": quality["refactoring_comparison"],
        "git_history": history,
    }
    filenames = {"sqlite": "evidence_sqlite.txt", "duckdb": "evidence_duckdb.txt",
                 "equipment": "evidence_equipment.txt", "migration": "evidence_migration.txt"}
    for key, filename in filenames.items():
        session = evidence["sessions"][key]
        (DEMO / filename).write_text(
            session["command"] + "\n" + session["transcript"],
            encoding="utf-8",
        )
    (DEMO / "walkthrough_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print("Recorded successful legacy, SQLite, DuckDB, equipment, and migration commands.")


if __name__ == "__main__":
    main()

