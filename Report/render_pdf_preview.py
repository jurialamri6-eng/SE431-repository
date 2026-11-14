"""Render a multipage contact sheet for human visual review."""

from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw


root = Path(__file__).resolve().parents[1]
pdf = root / "Report" / "SE431_Final_Report.pdf"
destination = root / "Evidence" / "report_contact_sheet.png"
document = pymupdf.open(pdf)
thumbnails = []
scale = 0.55
for page in document:
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    thumbnails.append(
        Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples, "raw", "RGB", pixmap.stride, 1)
    )

cell_width, cell_height, columns = 320, 430, 3
rows = (len(thumbnails) + columns - 1) // columns
sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), (220, 227, 232))
draw = ImageDraw.Draw(sheet)
for index, image in enumerate(thumbnails):
    image.thumbnail((cell_width - 20, cell_height - 32))
    x = (index % columns) * cell_width + 10
    y = (index // columns) * cell_height + 24
    sheet.paste(image, (x, y))
    draw.text(((index % columns) * cell_width + 12, (index // columns) * cell_height + 6), f"Page {index + 1}", fill=(20, 45, 65))
sheet.save(destination)
print(f"Rendered {len(document)} pages to {destination}")
