"""Build the editable diagrams.net file from the original pages and project figures."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "Project_References" / "library.drawio"
OUTPUT = ROOT / "Drawio_Diagrams" / "SE431_Architecture.drawio"

INK = "#163047"
BLUE = "#14577B"
LINE = "#456175"
BASE = "#F4F7FA"
HIGHLIGHT = "#E7F3F7"
SUCCESS = "#EAF4ED"
REJECTED = "#FBF0E8"


class Diagram:
    def __init__(self, file: ET.Element, key: str, name: str, title: str) -> None:
        page = ET.SubElement(file, "diagram", id=key, name=name)
        model = ET.SubElement(
            page, "mxGraphModel", grid="1", gridSize="10", guides="1", connect="1",
            page="1", pageScale="1", pageWidth="1090", pageHeight="515",
            background="#FFFFFF",
        )
        self.root = ET.SubElement(model, "root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self.text("title", title, 22, 18, 1046, 50, 35, bold=True, align="left")

    @staticmethod
    def geometry(cell: ET.Element, x: int, y: int, w: int, h: int) -> None:
        ET.SubElement(cell, "mxGeometry", {
            "x": str(x), "y": str(y), "width": str(w), "height": str(h),
            "as": "geometry",
        })

    def text(
        self, key: str, label: str, x: int, y: int, w: int, h: int, size: int,
        *, parent: str = "1", bold: bool = False, align: str = "center",
    ) -> None:
        cell = ET.SubElement(
            self.root, "mxCell", id=key, value=label, parent=parent, vertex="1",
            connectable="0", style=(
                f"text;html=0;fillColor=none;strokeColor=none;align={align};"
                f"verticalAlign=middle;whiteSpace=wrap;spacing=0;fontFamily=Arial;"
                f"fontStyle={int(bold)};fontSize={size};fontColor={INK};"
            ),
        )
        self.geometry(cell, x, y, w, h)

    def box(
        self, key: str, title: str, detail: str, x: int, y: int, w: int, h: int,
        *, fill: str = BASE, title_size: int = 28, detail_size: int = 23,
    ) -> None:
        cell = ET.SubElement(
            self.root, "mxCell", id=key, vertex="1", parent="1", style=(
                f"rounded=1;arcSize=10;strokeWidth=2;strokeColor={LINE};"
                f"fillColor={fill};whiteSpace=wrap;html=0;container=1;"
            ),
        )
        self.geometry(cell, x, y, w, h)
        if detail:
            self.text(f"{key}-title", title, 8, 7, w - 16, 38, title_size,
                      parent=key, bold=True)
            self.text(f"{key}-detail", detail, 8, 45, w - 16, h - 50, detail_size,
                      parent=key)
        else:
            self.text(f"{key}-title", title, 8, 4, w - 16, h - 8, title_size,
                      parent=key, bold=True)

    def edge(
        self, source: str, target: str, *, points: tuple[tuple[int, int], ...] = (),
        start: tuple[float, float] = (1, 0.5), end: tuple[float, float] = (0, 0.5),
    ) -> None:
        cell = ET.SubElement(
            self.root, "mxCell", id=f"edge-{source}-{target}", edge="1", parent="1",
            source=source, target=target, style=(
                f"edgeStyle=none;rounded=0;endArrow=block;endFill=1;endSize=11;"
                f"strokeWidth=2.5;strokeColor={BLUE};exitX={start[0]};exitY={start[1]};"
                f"entryX={end[0]};entryY={end[1]};"
            ),
        )
        geometry = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        if points:
            array = ET.SubElement(geometry, "Array", {"as": "points"})
            for x, y in points:
                ET.SubElement(array, "mxPoint", x=str(x), y=str(y))


def current(file: ET.Element) -> None:
    p = Diagram(file, "current-architecture", "3 Current Architecture", "Current Library System")
    p.box("menu", "main()", "Console menu", 22, 231, 232, 94, fill=HIGHLIGHT)
    p.box("db", "library.db", "SQLite\nmembers, books, loans", 794, 207, 274, 142,
          fill=HIGHLIGHT)
    for i, (key, title, detail) in enumerate((
        ("setup", "setup()", "Create and seed tables"),
        ("search", "search_books()", "Find books and print"),
        ("borrow", "borrow()", "Check and create loan"),
        ("return", "return_book()", "Close loan and fine"),
    )):
        y = 91 + i * 100
        p.box(key, title, detail, 359, y, 326, 84)
        center = y + 42
        p.edge("menu", key, points=((306, 278), (306, center)))
        p.edge(key, "db", points=((736, center), (736, 278)))


def multiple_copies(file: ET.Element) -> None:
    p = Diagram(file, "multiple-copies", "4 MR-01 Multiple Copies", "MR-01: Multiple Copies")
    for i, (key, title, detail, fill) in enumerate((
        ("start", "Start", "2 / 2 available", HIGHLIGHT),
        ("borrow", "Borrow twice", "0 / 2 available", BASE),
        ("reject", "Third request", "Rejected\n0 / 2 available", REJECTED),
        ("return", "Return loan 1", "1 / 2 available", SUCCESS),
    )):
        p.box(key, title, detail, 22 + i * 265, 139, 251, 154, fill=fill)
    p.edge("start", "borrow")
    p.edge("borrow", "reject")
    p.edge("reject", "return")
    p.text("invariant", "A successful borrow or return updates the loan and stock in one transaction.",
           22, 333, 1046, 48, 24, bold=True)


def reengineered(file: ET.Element) -> None:
    p = Diagram(file, "final-architecture", "5 Final Architecture", "Final System: Storage Adapters")
    p.box("cli", "cli.py", "Console menu", 22, 111, 245, 108)
    p.box("service", "LendingService", "Loan rules and stock", 325, 111, 315, 108, fill=HIGHLIGHT)
    p.box("port", "Storage", "Repository contract", 713, 111, 355, 108, fill=HIGHLIGHT)
    p.box("sqlite", "SQLiteRepository", "SQLite", 396, 347, 308, 109, title_size=27)
    p.box("duckdb", "DuckDBRepository", "DuckDB", 752, 347, 316, 109, title_size=27)
    p.edge("cli", "service")
    p.edge("service", "port")
    p.edge("port", "sqlite", start=(0.5, 1), end=(0.5, 0),
           points=((890, 282), (550, 282)))
    p.edge("port", "duckdb", start=(0.5, 1), end=(0.5, 0),
           points=((890, 282), (910, 282)))


def reusable(file: ET.Element) -> None:
    p = Diagram(file, "reuse-architecture", "6 Reusable Domain", "Shared Lending for Books and Equipment")
    p.box("books", "Book policy", "3 open loans · 14 days", 54, 93, 403, 105)
    p.box("equipment", "Equipment demo policy", "1 open loan · 7 days", 633, 93, 403, 105)
    p.box("core", "LendingService", "Member checks, loans, stock and returns",
          228, 254, 634, 107, fill=HIGHLIGHT)
    p.box("member", "Member", "", 54, 423, 274, 62)
    p.box("item", "BorrowableItem", "", 409, 423, 272, 62)
    p.box("loan", "Loan", "", 762, 423, 274, 62)
    p.edge("books", "core", start=(0.5, 1), end=(0.24, 0),
           points=((256, 226), (380, 226)))
    p.edge("equipment", "core", start=(0.5, 1), end=(0.76, 0),
           points=((834, 226), (710, 226)))
    p.edge("core", "member", start=(0.5, 1), end=(0.5, 0),
           points=((545, 391), (191, 391)))
    p.edge("core", "item", start=(0.5, 1), end=(0.5, 0))
    p.edge("core", "loan", start=(0.5, 1), end=(0.5, 0),
           points=((545, 391), (899, 391)))


def main() -> None:
    source = ET.parse(REFERENCE).getroot()
    pages = source.findall("diagram")
    if len(pages) != 2:
        raise ValueError("Expected the supplied two-page library.drawio source.")
    file = ET.Element("mxfile", dict(source.attrib))
    for page in pages:
        file.append(deepcopy(page))
    for build in (current, multiple_copies, reengineered, reusable):
        build(file)
    file.set("pages", str(len(file.findall("diagram"))))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(file).write(OUTPUT, encoding="utf-8", xml_declaration=True)
    print(f"Saved {OUTPUT} with two supplied pages and four editable project diagrams.")


if __name__ == "__main__":
    main()

