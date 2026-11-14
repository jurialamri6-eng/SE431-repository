"""Refresh Word fields and export the report using installed Microsoft Word."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
SCRIPT = FOLDER / "refresh_docx_fields.ps1"
EXPORT = FOLDER / "export_report_pdf.py"


def main() -> None:
    if not SCRIPT.exists():
        raise FileNotFoundError(SCRIPT)
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT)],
        check=True,
    )
    subprocess.run([sys.executable, str(EXPORT)], check=True)


if __name__ == "__main__":
    main()
