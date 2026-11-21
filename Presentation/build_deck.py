"""Build a simple student presentation from the official UPM PowerPoint template."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "Project_References" / "UPM_Official_Presentation_Template.pptx"
OUTPUT = ROOT / "Presentation" / "SE431_Presentation.pptx"
METRICS = json.loads((ROOT / "Evidence" / "quality_metrics.json").read_text(encoding="utf-8"))
REVIEW = json.loads((ROOT / "Documentation" / "review_status.json").read_text(encoding="utf-8-sig"))
TEAM = REVIEW["team"]
REPO = REVIEW["repository"]
TEAM_MEMBERS = ", ".join(f"{m['name']} ({m['id']})" for m in TEAM["members"]) or "Not supplied"
COMMIT_COUNT = REPO["original_stages"] + REPO["review_commits"]
REPOSITORY = REPO["url"] or "Repository link not supplied"
BLUE = RGBColor(17, 89, 129)
TEAL = RGBColor(19, 187, 183)
INK = RGBColor(35, 48, 58)
GRAY = RGBColor(95, 108, 118)
WHITE = RGBColor(255, 255, 255)


def set_paragraph_font(paragraph, size: float, color=INK, bold=False, name="Arial") -> None:
    for run in paragraph.runs:
        run.font.name = name
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.bold = bold


def set_placeholder(placeholder, lines: list[str], size: float, color=INK, bullets=False) -> None:
    frame = placeholder.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.08)
    frame.margin_right = Inches(0.06)
    frame.margin_top = Inches(0.06)
    frame.margin_bottom = Inches(0.04)
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.level = 0
        paragraph.space_after = Pt(14 if bullets else 7)
        paragraph.line_spacing = 1.06
        set_paragraph_font(paragraph, size, color)


def add_plain_text(slide, content: str, x: float, y: float, w: float, h: float,
                   size: float = 17, color=INK, bold=False, align=PP_ALIGN.LEFT,
                   valign=MSO_ANCHOR.TOP, margin: float = 0.04):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(margin)
    frame.margin_top = frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = valign
    for index, line in enumerate(content.split("\n")):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.alignment = align
        paragraph.space_after = Pt(7)
        paragraph.line_spacing = 1.08
        set_paragraph_font(paragraph, size, color, bold)
    return shape


def add_bullet_box(slide, lines: list[str], x: float, y: float, w: float, h: float,
                   size: float = 17, color=INK, gap: float = 11):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.02)
    frame.margin_right = Inches(0.02)
    frame.margin_top = Inches(0.02)
    frame.margin_bottom = Inches(0.02)
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = "•  " + line
        paragraph.space_after = Pt(gap)
        paragraph.line_spacing = 1.04
        set_paragraph_font(paragraph, size, color)
    return shape


def add_title(slide, title: str, page_number: int | None = None):
    title_shape = slide.shapes.title
    title_shape.text = title
    title_shape.text_frame.word_wrap = True
    for paragraph in title_shape.text_frame.paragraphs:
        set_paragraph_font(paragraph, 26, BLUE, True)
    if page_number is not None:
        add_plain_text(slide, str(page_number), 1.92, 6.96, 0.35, 0.28, size=9, color=BLUE)


def add_text_slide(prs, title: str, bullets: list[str], page: int, size: float = 20):
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    add_title(slide, title, page)
    body = slide.placeholders[1]
    set_placeholder(body, bullets, size, bullets=True)
    return slide


def add_title_only(prs, title: str, page: int):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    add_title(slide, title, page)
    return slide


def add_table(slide, rows: list[list[str]], x: float, y: float, w: float, h: float,
              widths: list[float] | None = None, font_size: float = 14):
    shape = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(h))
    table = shape.table
    table.style = "Table Grid"
    if widths:
        for col, width in zip(table.columns, widths):
            col.width = Inches(width)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.text = value
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.05)
            cell.margin_bottom = Inches(0.05)
            if r == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = BLUE
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE
            for paragraph in cell.text_frame.paragraphs:
                paragraph.space_after = Pt(2)
                for run in paragraph.runs:
                    run.font.name = "Arial"
                    run.font.size = Pt(font_size - 0.5 if r == 0 else font_size)
                    run.font.bold = r == 0
                    run.font.color.rgb = WHITE if r == 0 else INK
    return table


def add_image_fit(slide, path: Path, x: float, y: float, max_w: float, max_h: float):
    from PIL import Image
    with Image.open(path) as image:
        ratio = image.width / image.height
    width = min(max_w, max_h * ratio)
    height = width / ratio
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(width), height=Inches(height))


def add_figure_slide(prs, page: int, title: str, stem: str, caption: str):
    slide = add_title_only(prs, title, page)
    picture = add_image_fit(slide, ROOT / "Drawio_Diagrams" / f"{stem}.png", 0.8, 1.77, 11.73, 4.75)
    picture.left = (prs.slide_width - picture.width) // 2
    add_plain_text(slide, caption, 0.85, 6.57, 11.63, 0.32,
                   size=13.5, color=GRAY, align=PP_ALIGN.CENTER)
    return slide


def remove_unused_template_slides(prs: Presentation) -> None:
    slide_ids = prs.slides._sldIdLst
    for slide_id in list(slide_ids)[2:]:
        relationship_id = slide_id.rId
        slide_ids.remove(slide_id)
        prs.part.drop_rel(relationship_id)


def format_cover(prs: Presentation) -> None:
    slide = prs.slides[0]
    # The official template includes the bilingual UPM logo. Remove its corrupted
    # legacy text-box glyphs so the logo remains the only institution mark.
    for shape in list(slide.shapes):
        if shape.name == "TextBox 9":
            shape._element.getparent().remove(shape._element)
    add_plain_text(slide, "College of Computer and Cyber Sciences\nDepartment of Computer Science",
                   8.4, 3.62, 4.65, 0.48, size=10.5, color=GRAY)
    add_plain_text(slide, "Legacy Library System", 8.4, 4.18, 4.65, 0.65,
                   size=24, color=BLUE, bold=True)
    add_plain_text(
        slide,
        "SE431: Software Maintenance and Evolution\nFall 2026 | Review copy\n"
        f"Team number: {TEAM['number'] or 'Not supplied'}\n"
        f"Members and IDs: {TEAM_MEMBERS}\n"
        f"Instructor: {TEAM['instructor'] or 'Not supplied'}",
        8.4, 4.92, 4.65, 1.82, size=13.5, color=INK,
    )


def build() -> None:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Official UPM PowerPoint template was not found: {TEMPLATE}")
    prs = Presentation(TEMPLATE)
    if len(prs.slides) < 4:
        raise ValueError("The official template does not contain its expected cover and Bismillah pages")
    remove_unused_template_slides(prs)
    format_cover(prs)
    prs.core_properties.title = "SE431 Legacy Library System: Course Project"
    prs.core_properties.subject = "Program comprehension, maintenance, refactoring, reuse, and quality evaluation"
    prs.core_properties.author = "SE431 review copy"

    # 1 and 2 are the official cover and Bismillah pages.
    add_text_slide(prs, "Project objective and original requirements", [
        "Study the supplied legacy library program before changing it.",
        "Only active members may borrow books.",
        "A member may have at most three open book loans.",
        "A book must be available. The normal loan period is 14 days.",
        "Late returns receive a fine, and members can search for books.",
        "The project covers comprehension, maintenance requests, refactoring, reuse, quality, and Git history.",
    ], 1, size=19)

    add_figure_slide(
        prs, 2, "Phase 1: current architecture", "Current_Architecture_Readable",
        "Figure 1. The console menu calls four functions that use the same SQLite database.",
    )

    slide = add_title_only(prs, "Phase 1: responsibilities and problems", 3)
    add_table(slide, [
        ["Function", "Responsibility in the supplied code"],
        ["setup()", "Opens SQLite, creates tables, inserts sample rows."],
        ["search_books()", "Searches titles/authors and prints results."],
        ["borrow()", "Checks member, availability, limit, dates; writes loan."],
        ["return_book()", "Calculates fine, closes loan, restores availability."],
        ["main()", "Reads the menu and calls the other functions."],
    ], 0.95, 1.8, 11.4, 3.35, [2.3, 9.1], 16)
    add_bullet_box(slide, [
        "Problems found: SQL is spread across functions; input/output and rules are mixed; policy values are unnamed; tuples depend on column order.",
        "A Boolean availability value cannot record multiple copies, and the original schema declares no foreign keys.",
    ], 1.0, 5.4, 11.2, 1.25, size=15, gap=5)

    slide = add_title_only(prs, "Phase 2: maintenance requests", 4)
    add_table(slide, [
        ["Request", "Classification and impact", "Implementation"],
        ["MR-01: multiple copies", "Perfective/additive. Changes item stock, borrowing, return, and migration logic; replaces the availability flag with total and available copy counts.", "Implemented with transactional stock updates and loan-ID selection when a member has multiple loans for one title."],
        ["MR-02: replace database", "Adaptive. Changes persistence, engine selection, and migration; the member, book, loan, and lending rules remain stable.", "Implemented with SQLite and DuckDB adapters behind one storage port. Migration writes to a separate target and validates data."],
    ], 0.95, 1.85, 11.4, 3.65, [2.2, 4.6, 4.6], 14)
    add_plain_text(slide, "The analysis is required. Implementation of both requests earns bonus credit.",
                   1.0, 5.75, 11.2, 0.72, size=15, color=GRAY)

    add_figure_slide(
        prs, 5, "MR-01: multiple book copies", "Multiple_Copies_Design",
        "Figure 2. Two loans use both copies. Returning the first loan makes one copy available.",
    )
    add_figure_slide(
        prs, 6, "MR-02: the final storage design", "Reengineered_Architecture",
        "Figure 3. Choose SQLite or DuckDB at startup. Both repositories implement Storage.",
    )

    slide = add_title_only(prs, "Phase 3: refactoring and behavior", 7)
    add_table(slide, [
        ["Change", "Before", "After"],
        ["Decompose borrow()", "Eligibility, stock, dates, writes, and output were together.", "Extracted named member and item checks."],
        ["Separate console work", "Menu input and printed messages shared the lending flow.", "cli.py handles the menu; LendingService returns outcomes."],
        ["Use named data and extract fine calculation", "Rows used tuple positions; return logic did the arithmetic and SQL.", "Repositories return named records; a helper calculates completed-day fines."],
    ], 0.95, 1.85, 11.4, 3.85, [2.8, 4.2, 4.4], 14)
    add_bullet_box(slide, [
        "Single-copy behavior was compared with a normalized legacy fixture after fixing the supplied syntax and entry-point defects.",
        "Both engines preserve the book menu. The review also checks accented search and the returned loan flag.",
    ], 1.0, 5.95, 11.2, 0.8, size=15, gap=2)

    add_figure_slide(
        prs, 8, "Phase 4: reusable lending domain", "Reusable_Domain_Architecture",
        "Figure 4. The same service applies a different policy to books and demonstration equipment.",
    )

    slide = add_title_only(prs, "Phase 5: quality and test evidence", 9)
    stages = [METRICS[key] for key in ("legacy", "post_maintenance_pre_refactor", "reengineered")]
    text = (ROOT / "Evidence" / "test-results.txt").read_text(encoding="utf-8")
    test_count = re.search(r"Ran (\d+) tests? in", text).group(1)
    rows = [
        ["Automated measure", "Legacy", "After Maintenance", "After Refactoring"],
        ["Physical LOC", *[str(stage["loc"]) for stage in stages]],
        ["Logical LOC", *[str(stage["lloc"]) for stage in stages]],
        ["Functions / classes", *[f"{stage['function_count']} / {stage['class_count']}" for stage in stages]],
        ["Mean / max complexity", *[f"{stage['cyclomatic']['average']} / {stage['cyclomatic']['maximum']}" for stage in stages]],
        ["borrow() complexity", *[str(stage["cyclomatic"]["borrow"]) for stage in stages]],
    ]
    add_table(slide, rows, 0.95, 1.8, 11.4, 3.55, [3.50, 2.15, 2.87, 2.88], 16)
    add_bullet_box(slide, [
        f"{test_count} tests passed. Both engines agree on the accented search and successful return state.",
        "Manual review counted six legacy issues and one remaining stock invariant.",
        "SQL stays in storage and migration. LendingService calls the storage interface.",
    ], 1.0, 5.60, 11.2, 1.25, size=14.5, gap=4)

    slide = add_title_only(prs, "Project plan, tracking, and teamwork", 10)
    tasks = REVIEW["tasks"]
    add_table(slide, [
        ["Milestone", "Recorded date", "Status and evidence"],
        [tasks[0]["task"], tasks[0]["actual"], tasks[0]["evidence"]],
        [tasks[1]["task"], tasks[1]["actual"], tasks[1]["evidence"]],
        [tasks[2]["task"], tasks[2]["actual"], tasks[2]["evidence"]],
        ["07–08: technical and delivery review", tasks[4]["actual"], "Local tests, measurements, slides, recording and bundle"],
        ["Team records and submission", tasks[-1]["actual"] or "Not supplied", tasks[-1]["status"]],
    ], 0.95, 1.8, 11.4, 3.6, [3.50, 2.80, 5.10], 15)
    add_bullet_box(slide, [
        f"The Teams deadline is {REVIEW['course_deadline']}.",
        "Appendix C records task resources, planned and actual dates, status and proof.",
        ("Team collaboration records are listed in Appendix C." if REVIEW["collaboration"] else
         "Team owners, meeting dates, member contributions and feedback have not been supplied."),
    ], 1.0, 5.65, 11.2, 1.15, size=14, gap=3)

    slide = add_title_only(prs, "Phase 6: Git history and learning", 11)
    add_table(slide, [
        ["Commit", "Stage"],
        ["01", "Initial legacy system"],
        ["02", "Program comprehension analysis"],
        ["03", "Multiple copies and DuckDB migration"],
        ["04", "Borrowing refactor and storage isolation"],
        ["05", "Equipment lending reuse analysis"],
        ["06", "Final reengineered system"],
        ["07", "Search, return and setup corrections"],
        ["08", "Review documents and live recording"],
    ], 0.95, 1.8, 5.35, 4.8, [1.2, 4.15], 14)
    add_plain_text(slide, "New knowledge applied", 6.75, 1.8, 5.4, 0.45, size=20, color=BLUE, bold=True)
    add_bullet_box(slide, [
        "Database transactions and DB-API: Python sqlite3 and DuckDB documentation; applied in adapters and migration checks.",
        "Refactoring: Fowler and SEBoK; applied to borrow(), CLI separation, and named records.",
        "Complexity measurement: Radon documentation; applied in the reproducible quality report.",
        f"The bundle has {COMMIT_COUNT} commits. {REPOSITORY}. Earlier authorship is retained.",
    ], 6.75, 2.35, 5.45, 4.25, size=15, gap=10)

    slide = add_text_slide(prs, "Demo and discussion", [
        "The screen recording follows the live terminal, both engines, code changes, tests, metrics and Git history.",
        "Why can the old availability flag not give a copy count? It records only available or unavailable, so ambiguous stock needs a verified inventory.",
        "How is the last copy protected? The stock check and loan update share a transaction; concurrent tests allow only one request to succeed.",
        "What behavior was preserved? The single-copy fixture compares search, borrowing, due dates, and completed-day fines after syntax repair.",
        "The migration used a generated legacy fixture. The review demonstrates École and the saved return status.",
    ], 12, size=17)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    print(f"Saved {OUTPUT} ({len(prs.slides)} slides) using {TEMPLATE.name}")


if __name__ == "__main__":
    build()
