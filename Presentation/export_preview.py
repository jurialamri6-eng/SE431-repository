"""Export the PowerPoint with the installed LibreOffice command line."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
SOURCE = FOLDER / "SE431_Presentation.pptx"
OUTPUT = FOLDER / "SE431_Presentation_preview.pdf"
SOFFICE = shutil.which("soffice") or Path(r"C:\Program Files\LibreOffice\program\soffice.exe")


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    if not Path(SOFFICE).exists():
        raise FileNotFoundError(f"LibreOffice executable not found: {SOFFICE}")
    with tempfile.TemporaryDirectory(prefix="se431-presentation-export-") as temp:
        root = Path(temp)
        out_dir = root / "out"
        out_dir.mkdir()
        profile = root / "profile"
        command = [
            str(SOFFICE), "--headless", "--nologo", "--nodefault", "--norestore",
            f"-env:UserInstallation={profile.as_uri()}", "--convert-to", "pdf:impress_pdf_Export",
            "--outdir", str(out_dir), str(SOURCE),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        generated = out_dir / "SE431_Presentation.pdf"
        if result.returncode != 0 or not generated.is_file() or generated.stat().st_size == 0:
            raise RuntimeError(
                f"LibreOffice PowerPoint export failed (code {result.returncode}).\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        shutil.copy2(generated, OUTPUT)
    print(f"Saved {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
