"""Run the project walkthrough in a real console for a screen recording."""

from __future__ import annotations

import argparse
import ctypes
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from demo_walkthrough import (
    BOOK_SESSION, EQUIPMENT_SESSION, ENV, ROOT, SOURCE, record_session, run_migration,
)


CYAN = "\033[96m"
GREEN = "\033[92m"
AMBER = "\033[93m"
RESET = "\033[0m"
TITLE = "SE431 Live Terminal Review"
TIMELINE: Path | None = None


def chapter(heading: str, note: str) -> None:
    print(f"\033[2J\033[H{CYAN}SE431  |  UNIVERSITY OF PRINCE MUGRIN  |  LIVE TERMINAL{RESET}\n")
    print(f"{CYAN}{heading}{RESET}")
    print(note + "\n")
    if TIMELINE:
        with TIMELINE.open("a", encoding="utf-8") as events:
            events.write(json.dumps({"time": time.time(), "chapter": heading}) + "\n")


def command(args: list[str], cwd: Path = ROOT, *, show: bool = True) -> str:
    display = ["python" if arg == sys.executable else arg for arg in args]
    print(f"{GREEN}$ {' '.join(display)}{RESET}", flush=True)
    output = subprocess.run(
        args, cwd=cwd, env=ENV, encoding="utf-8", capture_output=True,
        timeout=90, check=True,
    ).stdout
    if show:
        print(output.strip(), flush=True)
    return output


def excerpt(source: str, pattern: str, count: int = 5) -> None:
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines) if re.search(pattern, line))
    for i in range(start, min(start + count, len(lines))):
        print(f"{i + 1:>3}  {lines[i]}")


def session(
    checkout: Path, engine: str, filename: str, steps: list, *,
    equipment: bool = False, legacy: bool = False,
) -> dict:
    noun = "Equipment" if equipment else "Book"
    args = ["legacy.legacy_system_executable"] if legacy else [
        "library_system", "--engine", engine, "--database", f"../runtime/{filename}",
    ]
    if equipment:
        args += ["--item-type", "equipment"]
    position = 0

    def live_step(event: dict) -> None:
        nonlocal position
        if position == 0:
            if legacy:
                chapter("01  |  RUN THE NORMALIZED LEGACY COPY",
                        "SQLite uses one availability flag. This run creates a small migration fixture.")
            elif equipment:
                chapter("05  |  REUSE THE LENDING SERVICE FOR EQUIPMENT",
                        "Demo policy: at most one equipment loan, due in seven days.")
            else:
                phase = "MR-01" if engine == "sqlite" else "MR-02"
                chapter(f"{phase}  |  SEARCH AND BORROW ON {engine.upper()}",
                        "The same title starts with two available copies.")
            print(f"{GREEN}$ python -m {' '.join(args)}{RESET}\n")
        elif position == 3 and not legacy and not equipment:
            chapter(f"CONTINUE ON {engine.upper()}  |  REJECT, RETURN, RECHECK",
                    "The third request fails. Returning loan #1 restores one copy.")
            print(f"{GREEN}$ python -m {' '.join(args)}{RESET}\n")

        lines = event["text"].strip().splitlines()
        first_choice = next(i for i, line in enumerate(lines) if line.startswith("Choice:"))
        print(f"{CYAN}{event['step']}{RESET}")
        for line in lines[first_choice:]:
            shade = AMBER if "unavailable" in line else RESET
            print(f"{shade}{line}{RESET}", flush=True)
            time.sleep(0.15)
        print()
        time.sleep(3.0 if not legacy else 3.5)
        position += 1

    return record_session(checkout, args, steps, noun, live_step)


def tests_and_metrics() -> None:
    chapter("QUALITY  |  RUN THE FULL TEST SUITE",
            "This command runs every test from Source_Code. It creates temporary databases.")
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    print(f"{GREEN}$ python {' '.join(cmd[1:])}{RESET}", flush=True)
    with subprocess.Popen(
        cmd, cwd=SOURCE, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8",
    ) as process:
        output = []
        for line in process.stdout:
            output.append(line)
            print(line.rstrip(), flush=True)
        if process.wait(timeout=12):
            raise RuntimeError("The live suite failed.")
    chapter("QUALITY  |  TEST RESULT AND RECOMPUTED METRICS",
            "The three columns isolate the effect of refactoring after maintenance.")
    test_result = re.search(r"Ran \d+ tests in [^\n]+\n\nOK", "".join(output))
    print(test_result.group(0), "\n")
    command([sys.executable, "tools/quality_metrics.py"], SOURCE, show=False)
    data = json.loads((ROOT / "Evidence" / "quality_metrics.json").read_text(encoding="utf-8"))
    code = [data[key] for key in ("legacy", "post_maintenance_pre_refactor", "reengineered")]
    print(f"\n{'Measurement':<27}  {'Legacy':>12}  {'After maintenance':>18}  {'After refactoring':>18}")
    rows = [
        ("Physical lines", [entry["loc"] for entry in code]),
        ("Logical lines", [entry["lloc"] for entry in code]),
        ("Functions", [entry["function_count"] for entry in code]),
        ("Classes", [entry["class_count"] for entry in code]),
        ("borrow() complexity", [entry["cyclomatic"]["borrow"] for entry in code]),
    ]
    for name, values in rows:
        print(f"{name:<27}  {values[0]:>12}  {values[1]:>18}  {values[2]:>18}")
    time.sleep(10)


def run() -> None:
    chapter("01  |  THE SUPPLIED PROGRAM",
            "One Python script combines terminal input, lending rules and direct SQLite queries.")
    command(["git", "grep", "-n", "-e", 'if name', "-e", '__name__', "HEAD", "--", "Source_Code/legacy"])
    print("\nThe original text stays in Git. The executable copy repairs indentation and the entry guard.")
    for path in sorted((SOURCE / "legacy").glob("*")):
        if path.suffix in {".txt", ".py"}:
            print(f"\n{path.name}")
            excerpt(path.read_text(encoding="utf-8"), r"^def setup", 4)
    time.sleep(10)

    with tempfile.TemporaryDirectory(prefix="se431-screen-demo-") as temp:
        checkout = Path(temp) / "Source_Code"
        shutil.copytree(SOURCE, checkout, ignore=shutil.ignore_patterns("__pycache__"))
        session(checkout, "sqlite", "", [
            ("Search the original catalog", ["1", "Clean Code"]),
            ("Create a sample loan", ["2", "S1", "1"]),
        ], legacy=True)
        session(checkout, "sqlite", "screen.sqlite3", BOOK_SESSION)
        session(checkout, "duckdb", "screen.duckdb", BOOK_SESSION)

        chapter("MR-02  |  MIGRATE THE LEGACY FIXTURE",
                "This fixture came from the normalized program, using demonstration data.")
        migration = run_migration(checkout)
        print(f"{GREEN}$ {migration['command']}{RESET}")
        print(migration["transcript"].strip())
        print("Source file unchanged:", migration["source_unchanged"])
        time.sleep(9)

        chapter("04  |  COMPARE BORROWING BEFORE AND AFTER",
                "The prototype mixed policy, SQL and messages. The service names its validation steps.")
        old = command(["git", "show", "cec6910:Source_Code/pre_refactor_system.py"], show=False)
        excerpt(old, r"member = connection.execute", 12)
        print()
        new = command(["git", "show", "1f08c9f:Source_Code/library_system/service.py"], show=False)
        excerpt(new, r"member = self.storage.get_member", 10)
        time.sleep(13)

        chapter("04  |  TWO MORE REFACTORINGS",
                "The command-line adapter handles input and output. The service uses named data and a fine helper.")
        file = SOURCE / "library_system"
        print("Source_Code/library_system/cli.py")
        excerpt((file / "cli.py").read_text(encoding="utf-8"), r"^def _handle_borrow", 9)
        print("\nSource_Code/library_system/service.py")
        excerpt((file / "service.py").read_text(encoding="utf-8"), r"def _fine_for_return", 4)
        print("\nMember, BorrowableItem and Loan hold named fields used by books and equipment.")
        time.sleep(10)

        session(checkout, "duckdb", "screen-equipment.duckdb", EQUIPMENT_SESSION, equipment=True)

    chapter("REVIEW FIXES  |  CHECK BOTH ENGINES",
            "Compare the accented search and the returned loan with the stored value.")
    command([sys.executable, "Demo/demo_regressions.py"])
    time.sleep(10)

    tests_and_metrics()

    chapter("GIT  |  SIX ORIGINAL STAGES AND THE REVIEW FIX",
            "The original authors and commit IDs remain in Git. The delivery snapshot is recorded after this run.")
    command(["git", "log", "--reverse", "--format=%h %as %s"])
    print()
    command(["git", "diff", "--stat", "cec6910", "1f08c9f", "--", "Source_Code/library_system"])
    time.sleep(11)

    chapter("GIT  |  INSPECT THE ACTUAL SEARCH FIX",
            "DuckDB folds ASCII letters in the repository to match the legacy SQLite search.")
    command(["git", "--no-pager", "diff", "--color=always", "-U2", "99175e3", "d89cd5f", "--",
             "Source_Code/library_system/duckdb_repository.py"])
    time.sleep(11)

    chapter("DONE  |  LOCAL VERIFICATION COMPLETE",
            "The recording used temporary databases. The team's repository link and contribution records belong in the submission.")
    time.sleep(6)


def main() -> None:
    global TIMELINE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", type=Path, help="Optional capture signal")
    parser.add_argument("--timeline", type=Path, help="Optional path for chapter timestamps")
    args = parser.parse_args()
    TIMELINE = args.timeline
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetConsoleTitleW(TITLE)
    if args.gate:
        start = time.monotonic()
        while not args.gate.exists():
            if time.monotonic() - start > 35:
                raise TimeoutError("The screen recorder did not start.")
            time.sleep(0.10)
    run()


if __name__ == "__main__":
    main()
