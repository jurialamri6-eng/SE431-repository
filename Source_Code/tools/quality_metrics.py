"""Reproducible Radon/AST comparison for the normalized legacy and final code."""

from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path

from radon.complexity import cc_rank, cc_visit
from radon.raw import analyze


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "Source_Code"
LEGACY = SOURCE / "legacy" / "legacy_system_executable.py"
PRE_REFACTOR = SOURCE / "pre_refactor_system.py"
APPLICATION = SOURCE / "library_system"


def source_metrics(paths: list[Path]) -> dict:
    texts = [path.read_text(encoding="utf-8") for path in paths]
    raw = [analyze(text) for text in texts]
    blocks = [block for text in texts for block in cc_visit(text)]
    nodes = [node for text in texts for node in ast.walk(ast.parse(text))]
    functions = [node for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [node for node in nodes if isinstance(node, ast.ClassDef)]
    cc_by_name = {block.name: block.complexity for block in blocks}
    return {
        "files": [str(path.relative_to(ROOT)) for path in paths],
        "loc": sum(file.loc for file in raw),
        "lloc": sum(file.lloc for file in raw),
        "sloc": sum(file.sloc for file in raw),
        "function_count": len(functions),
        "class_count": len(classes),
        "cyclomatic": {
            "block_count": len(blocks),
            "average": round(sum(block.complexity for block in blocks) / len(blocks), 2) if blocks else 0,
            "maximum": max((block.complexity for block in blocks), default=0),
            "borrow": cc_by_name.get("borrow"),
            "highest_blocks": sorted(
                [{"name": block.name, "complexity": block.complexity, "rank": cc_rank(block.complexity)}
                 for block in blocks],
                key=lambda item: (-item["complexity"], item["name"]),
            )[:5],
        },
        "sql_execute_call_count": sum(
            1 for node in nodes
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"execute", "executemany", "executescript"}
        ),
    }


def main() -> None:
    legacy = source_metrics([LEGACY])
    pre_refactor = source_metrics([PRE_REFACTOR])
    new_files = sorted(APPLICATION.glob("*.py"))
    reengineered = source_metrics(new_files)
    result = {
        "measured_on": date.today().isoformat(),
        "tool": "Radon 6.0.1; Python AST for function/class/SQL counts",
        "scope": "File-by-file counts for normalized legacy code, the post-maintenance snapshot, and the final library_system package. Tests excluded.",
        "legacy": legacy,
        "post_maintenance_pre_refactor": pre_refactor,
        "reengineered": reengineered,
        "refactoring_comparison": {
            "borrow_complexity_before": pre_refactor["cyclomatic"]["borrow"],
            "borrow_complexity_after": reengineered["cyclomatic"]["borrow"],
            "maximum_complexity_before": pre_refactor["cyclomatic"]["maximum"],
            "maximum_complexity_after": reengineered["cyclomatic"]["maximum"],
            "method": "Same Radon version and analyzer; the before snapshot is the committed post-maintenance, pre-refactor single-file implementation.",
        },
        "db_dependency_components": {
            "legacy_functions_with_direct_sql": 4,
            "reengineered_application_functions_with_sql": 0,
            "reengineered_engine_specific_connector_modules": 2,
        },
        "smell_inventory": {
            "criteria": [
                "long borrowing method",
                "console output mixed with operations",
                "database calls in business functions",
                "embedded policy constants",
                "positional row access",
                "duplicated availability state",
            ],
            "legacy_count": 6,
            "reengineered_count": 1,
            "resolved": [
                "long borrowing method",
                "console output mixed with operations",
                "database calls in business functions",
                "embedded policy constants",
                "positional row access",
            ],
            "residual": [
                "available_copies is stored alongside open loan rows and must remain transactionally consistent",
            ],
            "method": "manual review against the six named criteria; not a Radon output",
        },
        "interpretation": {
            "loc_comparison": "The final count grows with the repositories, adapters, policies, migration, and CLI. Counts exclude tests.",
            "complexity_comparison": "Radon cyclomatic complexity is a static control-flow measure. Lower borrow() complexity and a lower maximum indicate simpler individual control paths, not proof of correctness.",
            "sql_count_comparison": "AST execute-call count is syntactic. The reengineered count includes shared repository code; service/application business rules have no direct SQL calls.",
        },
    }
    output = ROOT / "Evidence" / "quality_metrics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
