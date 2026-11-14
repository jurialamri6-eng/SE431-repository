"""Restore whitespace lost in the supplied TXT for a behavior-only baseline."""

from __future__ import annotations

import argparse
from pathlib import Path


def normalize(source: str) -> str:
    lines = source.splitlines()
    output = [
        '"""Execution-normalized copy of the supplied legacy source. It only restores',
        'indentation and the standard Python module-entry guard; keep the raw TXT as',
        'the authoritative attachment and do not use this file as the final system.',
        '"""',
    ]
    inside_function = False
    for line in lines:
        if line.startswith("def "):
            inside_function = True
            output.append(line)
        elif line == 'if name == "main":':
            inside_function = False
            output.append('if __name__ == "__main__":')
        elif line == "main()" and output[-1] == 'if __name__ == "__main__":':
            output.append("    main()")
        elif inside_function and line:
            output.append("    " + line)
        else:
            output.append(line)
    return "\n".join(output) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.write_text(
        normalize(args.source.read_text(encoding="utf-8-sig")), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
