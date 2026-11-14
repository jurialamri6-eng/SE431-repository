"""Render all exported slides into a contact sheet for visual review."""

from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw


root = Path(__file__).resolve().parents[1]
document = pymupdf.open(Path(__file__).with_name("SE431_Presentation_preview.pdf"))
columns, cell_width, cell_height = 3, 480, 280
rows = (len(document) + columns - 1) // columns
sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), (220, 227, 232))
draw = ImageDraw.Draw(sheet)
for index, page in enumerate(document):
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(0.5, 0.5), alpha=False)
    image = Image.frombytes(
        "RGB", (pixmap.width, pixmap.height), pixmap.samples, "raw", "RGB", pixmap.stride, 1
    )
    image.thumbnail((cell_width - 16, cell_height - 28))
    x = (index % columns) * cell_width + 8
    y = (index // columns) * cell_height + 22
    sheet.paste(image, (x, y))
    draw.text(((index % columns) * cell_width + 8, (index // columns) * cell_height + 4), f"Slide {index + 1}", fill=(20, 45, 65))
destination = root / "Evidence" / "presentation_contact_sheet.png"
sheet.save(destination)
print(f"Rendered {len(document)} slides to {destination}")
