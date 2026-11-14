"""Build the editable SE431 report from verified project artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Report" / "SE431_Final_Report.docx"
METRICS = json.loads((ROOT / "Evidence" / "quality_metrics.json").read_text(encoding="utf-8"))

NAVY = "115981"
TEAL = "13BBB7"
PALE = "EAF4F5"
INK = "243746"
GRAY = "687782"


def _set_cell_shading(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    existing = props.find(qn("w:shd"))
    if existing is not None:
        props.remove(existing)
    shade = OxmlElement("w:shd")
    shade.set(qn("w:val"), "clear")
    shade.set(qn("w:fill"), fill)
    # Keep tcPr children in the order required by WordprocessingML: shading
    # comes before cell margins, text direction, vertical alignment, etc.
    following = {"noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark", "headers"}
    insert_at = next(
        (index for index, child in enumerate(props) if child.tag.split("}")[-1] in following),
        len(props),
    )
    props.insert(insert_at, shade)


def _set_repeat_table_header(row) -> None:
    props = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    props.append(repeat)


def _add_field(paragraph, instruction: str, fallback: str = "") -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = fallback
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, code, separate, text, end):
        run._r.append(element)


def _add_toc_field(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin.set(qn("w:dirty"), "true")
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = ' TOC \\o "1-2" \\h \\z \\u '
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "Updating contents…"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, code, separate, text, end):
        run._r.append(element)


def _add_rich_text(paragraph, text: str) -> None:
    cursor = 0
    for match in re.finditer(r"`([^`]+)`", text):
        if match.start() > cursor:
            paragraph.add_run(text[cursor : match.start()])
        run = paragraph.add_run(match.group(1))
        run.font.name = "Consolas"
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor.from_string(NAVY)
        cursor = match.end()
    if cursor < len(text):
        paragraph.add_run(text[cursor:])


def _add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run("SE431 • Fall 2026     |     ")
    _add_field(paragraph, "PAGE", "1")


def _add_caption(document: Document, label: str, text: str, number: int):
    p = document.add_paragraph(style="Caption")
    p.paragraph_format.keep_with_next = True
    p.add_run(label + " ")
    _add_field(p, f"SEQ {label} \\* ARABIC", str(number))
    p.add_run(": " + text)
    return p


def _set_page_layout(section, landscape: bool) -> None:
    if landscape:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = Inches(11)
        section.page_height = Inches(8.5)
        section.top_margin = Inches(0.48)
        section.bottom_margin = Inches(0.48)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)
        section.header_distance = Inches(0.22)
        section.footer_distance = Inches(0.22)
    else:
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(0.72)
        section.bottom_margin = Inches(0.68)
        section.left_margin = Inches(0.78)
        section.right_margin = Inches(0.78)
        section.header_distance = Inches(0.3)
        section.footer_distance = Inches(0.32)


def _add_landscape_figure(
    document: Document, heading: str, text: str, number: int, image_path: Path,
) -> None:
    if number == 1:
        _set_page_layout(document.add_section(WD_SECTION_START.NEW_PAGE), True)
        _heading(document, "Appendix B: Architecture and Design Diagrams", 1)
    else:
        document.add_page_break()
    _heading(document, heading, 2)
    caption = _add_caption(document, "Figure", text, number)
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(10)
    paragraph.paragraph_format.space_after = Pt(0)
    picture = paragraph.add_run().add_picture(str(image_path), width=Inches(9.85))
    picture._inline.docPr.set("descr", text)


def _table(document: Document, headers: list[str], rows: list[list[str]], widths=None) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    header_cells = table.rows[0].cells
    _set_repeat_table_header(table.rows[0])
    for index, header in enumerate(headers):
        cell = header_cells[index]
        cell.text = header
        _set_cell_shading(cell, NAVY)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(10)
    table.autofit = not bool(widths)
    if widths:
        for column, cell, width in zip(table.columns, header_cells, widths):
            column.width = Inches(width)
            cell.width = Inches(width)
    for row_index, values in enumerate(rows):
        row = table.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        cells = row.cells
        for index, value in enumerate(values):
            cells[index].text = ""
            _add_rich_text(cells[index].paragraphs[0], str(value))
            cells[index].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if row_index % 2 == 1:
                _set_cell_shading(cells[index], "F4F7F9")
            for paragraph in cells[index].paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.space_before = Pt(2)
                for run in paragraph.runs:
                    run.font.size = Pt(10)
        if widths:
            for cell, width in zip(cells, widths):
                cell.width = Inches(width)
    document.add_paragraph().paragraph_format.space_after = Pt(1)


def _p(document: Document, text: str, style=None):
    paragraph = document.add_paragraph(style=style)
    _add_rich_text(paragraph, text)
    return paragraph


def _heading(document: Document, text: str, level: int = 1):
    return document.add_heading(text, level=level)


def _configure(document: Document) -> None:
    section = document.sections[0]
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.68)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.32)

    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.08

    for style_name, size, color in (("Heading 1", 16, NAVY), ("Heading 2", 12, NAVY), ("Heading 3", 11, NAVY)):
        style = document.styles[style_name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(10 if style_name != "Heading 3" else 6)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.keep_with_next = True

    caption = document.styles["Caption"]
    caption.font.name = "Times New Roman"
    caption.font.size = Pt(11)
    caption.font.italic = True
    caption.font.color.rgb = RGBColor.from_string(GRAY)

    for level, indent in ((1, 0), (2, 0.22)):
        name = f"TOC {level}"
        try:
            style = document.styles[name]
        except KeyError:
            style = document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = normal
        style.font.name = "Times New Roman"
        style.font.size = Pt(10)
        style.font.color.rgb = RGBColor.from_string(INK)
        style.paragraph_format.left_indent = Inches(indent)
        style.paragraph_format.space_after = Pt(2)
        style.paragraph_format.tab_stops.add_tab_stop(
            Inches(6.45), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS
        )

    footer = section.footer.paragraphs[0]
    _add_page_number(footer)
    for run in footer.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor.from_string(GRAY)

    settings = document.settings.element
    zoom = settings.find(qn("w:zoom"))
    if zoom is not None:
        zoom.set(qn("w:val"), "bestFit")
        zoom.set(qn("w:percent"), "100")
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
    else:
        settings.remove(update)
    update.set(qn("w:val"), "true")
    following = {
        "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids",
        "mathPr", "attachedSchema", "themeFontLang", "clrSchemeMapping",
        "doNotIncludeSubdocsInStats",
    }
    insert_at = next(
        (index for index, child in enumerate(settings) if child.tag.split("}")[-1] in following),
        len(settings),
    )
    settings.insert(insert_at, update)


def _cover(document: Document) -> None:
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    logo = ROOT / "Report" / "assets" / "upm_logo.png"
    if logo.exists():
        p.add_run().add_picture(str(logo), width=Inches(2.2))
    for text, size, color, bold in (
        ("University of Prince Mugrin", 16, NAVY, True),
        ("College of Computer and Cyber Sciences", 11, GRAY, False),
        ("Department of Computer Science", 11, TEAL, True),
        ("SE431: Software Maintenance and Evolution", 14, NAVY, True),
        ("Fall 2026 Course Project", 11, TEAL, True),
        ("Legacy Library System", 19, NAVY, True),
        ("Maintenance, Refactoring, and Reengineering", 13, GRAY, False),
        ("Student Project Report", 11, GRAY, False),
    ):
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4 if size < 20 else 12)
        r = p.add_run(text)
        r.font.name = "Times New Roman"
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = RGBColor.from_string(color)
    document.add_paragraph()
    _table(
        document,
        ["Project information", "Value"],
        [
            ["Team number", "[TO BE PROVIDED]"],
            ["Team members (3–4 names and university IDs)", "[TO BE PROVIDED]"],
            ["Instructor / supervisor", "[TO BE PROVIDED]"],
            ["Review date", "19 November 2026"],
        ],
        [2.7, 3.8],
    )
    note = document.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = note.add_run("Complete the team fields and add genuine group-work records before submission.")
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor.from_string(GRAY)
    document.add_page_break()


def _front_matter(document: Document) -> None:
    title = document.add_paragraph()
    title.paragraph_format.space_after = Pt(10)
    title_run = title.add_run("Contents")
    title_run.font.name = "Times New Roman"
    title_run.font.size = Pt(16)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor.from_string(NAVY)
    _add_toc_field(document.add_paragraph())
    document.add_page_break()


def build() -> None:
    doc = Document()
    _configure(doc)
    _cover(doc)
    _front_matter(doc)
    start = len(doc.element.body) - 1
    old = METRICS["legacy"]
    before = METRICS["post_maintenance_pre_refactor"]
    final = METRICS["reengineered"]
    tests = re.search(
        r"Ran (\d+) tests? in", (ROOT / "Evidence" / "test-results.txt").read_text(encoding="utf-8")
    )
    if tests is None:
        raise ValueError("A current test transcript is required to build the report.")
    test_count = tests.group(1)

    _heading(doc, "1. Introduction and Decision", 1)
    _p(doc, "This project studies and updates the Python library program supplied with SE431. The program uses a terminal menu to search, borrow and return books. We chose to maintain and reengineer it because the six core rules were already present, while its single script made changing those rules and replacing SQLite difficult. Keeping the working rules and separating the code was enough to meet both change requests [1], [2].")
    _p(doc, "The source text lost indentation and contains an invalid module guard. We kept the supplied text and made a separate executable copy by restoring syntax and the entry point. The analysis follows the original function calls, SQL statements and data updates. We used the executable copy to check legacy behavior on sample data [2], [8].")

    _heading(doc, "2. Phase 1: Program Comprehension", 1)
    _heading(doc, "2.1 Requirements and Business Rules", 2)
    _table(doc, ["Requirement", "What the original code does"], [
        ["Active members", "Read the member record and require status ACTIVE."],
        ["Maximum of three books", "Count open loans for the member. Reject at three."],
        ["Availability", "Check the book's availability flag before creating a loan."],
        ["Fourteen days", "Add 14 days to the date and time of borrowing."],
        ["Late fine", "Print one fine unit per completed overdue day."],
        ["Book search", "Match title or author and show stock. SQL wildcards still work."],
    ], [2.12, 4.82])
    _p(doc, "The order of checks matters. The program checks the member, reads the title, checks availability and then checks the loan limit. An unsuccessful request makes no changes. A return closes an open loan and makes the title available again. Fine payment and login are outside the code's responsibilities.")

    _heading(doc, "2.2 Components, Data and Dependencies", 2)
    _table(doc, ["Function", "Responsibility", "Direct dependency"], [
        ["main()", "Read menu input and dispatch operations.", "Console and other functions"],
        ["setup()", "Open the connection and create and seed tables.", "sqlite3 and all three tables"],
        ["search_books()", "Read and print matching books.", "books and console"],
        ["borrow()", "Check rules, create a loan and change availability.", "members, books, loans and datetime"],
        ["return_book()", "Close the loan, restore availability and calculate a fine.", "books, loans and datetime"],
    ], [1.27, 3.17, 2.50])
    _p(doc, "Figure 1 shows how the console reaches the database. All operations share a SQLite connection. The members table stores identity and status. Books stores title, author and availability. Loans stores the member and book IDs, two dates and the returned flag. Foreign keys are implied by the SQL but are absent from the original table declarations.")
    _p(doc, "For example, borrowing reads a member and a book before writing an ISO date string to the loans table. Returning reads that date and reopens availability. If the book update failed after the loan write, the original code had no explicit rollback path to handle the error.")
    _p(doc, "We identified six problems. The long borrow function mixes eligibility, dates, SQL and messages. Console output is mixed with business steps. SQL is spread across four functions. Loan limits and dates are hard-coded. Positional tuples tie code to column order. Book availability duplicates state carried by open loans. These problems increase the work needed to change storage and make parts of the program difficult to test on their own.")

    _heading(doc, "3. Phase 2: Maintenance Requests", 1)
    _heading(doc, "3.1 MR-01: Multiple Book Copies", 2)
    _p(doc, "MR-01 is perfective maintenance because it improves how the library handles stock. It is also additive in the SWEBOK classification because it adds behavior [3]. The old availability flag can represent at most one copy. The new items table records total and available copies, and every open loan reserves one copy. This affects setup, search, borrow, return and the books and loans data. The member table and three-loan rule keep their original purpose.")
    _p(doc, "The implementation updates the loan and stock in the same transaction. Two members can borrow copies of the same title while stock lasts. When a member borrows the same title twice, each loan counts toward the limit and the loan ID identifies which copy to return. With two copies of Clean Code, the third request was rejected and returning the first loan raised availability from zero to one. Figure 2 shows this run.")

    _heading(doc, "3.2 MR-02: Replace the Database", 2)
    _p(doc, "MR-02 is adaptive maintenance. It changes the storage engine while keeping the book rules [3]. The design gives the service one storage interface. SQLite and DuckDB implement its operations. Startup selects one engine, so a request writes to one database. Figure 3 shows the boundary between the console, the service and the adapters [5], [6].")
    _p(doc, "The change affects database setup, every operation that reads or writes data, and all three original tables. Migration maps members, books and loans to the new schema. It preserves IDs and dates, checks counts and stock, and writes to a separate empty destination. The old Boolean flag cannot reveal how many copies were purchased, so a verified inventory is needed in ambiguous cases. We tested migration with databases built from the legacy schema. The supplied files did not contain a live library database.")
    _p(doc, "Both bonus changes are implemented. SQLite supported the search, two borrows, rejection and return in Figure 2. DuckDB supported the same book walkthrough and the equipment demonstration. In a migration rehearsal, the command reported two members, three items and one loan. A file hash matched before and after migration. This demonstrated the importer on one complete fixture. DuckDB writes in this console program are coordinated within a single process.")

    _heading(doc, "4. Phase 3: Refactoring", 1)
    _p(doc, "The baseline for refactoring is the post-maintenance program in stage 03. This avoids counting the new copy behavior and second engine as effects of refactoring. The refactor separates which rules are applied, how results are printed and how records are read.")
    _table(doc, ["Refactoring", "Change"], [
        ["Decompose borrow()", "Extract member and item checks. The main method still checks the loan limit and updates stock and the loan in one transaction."],
        ["Separate the console", "Move input and printed results to cli.py. LendingService returns outcomes independently of terminal input."],
        ["Replace positional records", "Map rows to named Member, BorrowableItem and Loan records so policy code can read fields by name."],
        ["Extract the fine calculation", "Use one helper to calculate completed overdue days and keep return logic focused on closing a loan."],
    ], [2.01, 4.93])
    _p(doc, "A regression check runs the same book inputs against the stage 03 prototype and the current command on both engines. It compares the prompts, results, stock and the selected loan, allowing for clock differences in the printed timestamps. Another test compares search, a 14-day due date and a late return against the normalized one-copy system. The equipment option opens a separate console mode.")
    _p(doc, "A valid borrow of Clean Code gets the same due date and loan message in both book versions. When the available count reaches zero, both versions reject another request. The fine test moves the clock past the due date so it can check one completed overdue day without waiting for a real loan to expire.")

    _heading(doc, "5. Phase 4: Reuse and Domain Engineering", 1)
    _p(doc, "Books and equipment share search, member validation, an availability count, loans, due dates and returns. The same LendingService uses the same storage interface for both. Member identifies the borrower, BorrowableItem identifies what is lent, and Loan records the transaction. The item key uses type and ID so a book and a projector can both use ID 1.")
    _table(doc, ["Variable feature", "Books", "Equipment example"], [
        ["Description", "Title and author", "Name and inventory description"],
        ["Loan policy", "3 open loans, 14 days", "1 open loan, 7 days"],
        ["Daily fine", "1 unit per overdue day", "0 units in the demo"],
    ], [2.23, 2.27, 2.44])
    _p(doc, "Figure 4 shows the two policies using the common service. The equipment values are examples in the configuration file. A laptop, projector, camera or lab instrument uses the same operations with its own metadata. The project uses sample inventory because the course handout leaves equipment rules and inventory open.")

    _heading(doc, "6. Phase 5: Quality Evaluation", 1)
    _p(doc, "We counted lines per Python file, used Python AST for function and class counts, and used Radon 6.0.1 for cyclomatic complexity [7]. The original column uses the normalized code. The final column covers the running package and excludes tests. Code smells and database dependencies were checked by reading the code.")
    _table(doc, ["Measure", "Legacy", "Final"], [
        ["Physical / logical LOC", f"{old['loc']} / {old['lloc']}", f"{final['loc']} / {final['lloc']}"],
        ["Functions / classes", f"{old['function_count']} / {old['class_count']}", f"{final['function_count']} / {final['class_count']}"],
        ["Average / maximum complexity", f"{old['cyclomatic']['average']} / {old['cyclomatic']['maximum']}", f"{final['cyclomatic']['average']} / {final['cyclomatic']['maximum']}"],
        ["borrow() complexity", str(old["cyclomatic"]["borrow"]), str(final["cyclomatic"]["borrow"])],
        ["Named code smells", "6 reviewed", "5 addressed, 1 remaining"],
        ["Database dependencies", "4 original functions issue SQL", "0 in LendingService. SQL and driver code sit in the repository, adapters and migration utility."],
    ], [2.48, 1.48, 2.98])
    _p(doc, f"Borrowing complexity falls from {before['cyclomatic']['borrow']} to {final['cyclomatic']['borrow']} compared with the post-maintenance prototype. Maximum complexity falls from {before['cyclomatic']['maximum']} to {final['cyclomatic']['maximum']} on that same comparison. Code size grows because the final program includes the adapters, data models, policies and migration. The remaining smell is the stored availability count alongside open loans. Transactions keep the two values in agreement.")
    _p(doc, f"The current run passed {test_count} tests. It covers both engines, book rules, fine rounding, open loan limits, concurrent requests for the last copy, rollback, equipment and migration. The code and measurements are in Source_Code, and the execution and quality records are in Evidence and Demo.")
    _p(doc, "The concurrency checks address two different risks. In one case, two requests compete for the last available copy. In the other, two requests would take the same member beyond the three-loan limit. In both cases only one request can succeed. The failure test checks that stock and the loan record are restored when an update fails.")

    _heading(doc, "7. Phase 6: Git History", 1)
    _table(doc, ["Stage", "Evidence of evolution"], [
        ["01", "Supplied legacy code and executable syntax repair."],
        ["02", "Program comprehension and maintenance design."],
        ["03", "Multiple copies, DuckDB and a migration prototype."],
        ["04", "Refactored borrowing and isolated storage."],
        ["05", "Equipment reuse analysis and shared domain examples."],
        ["06", "Final command, tests, measurements and delivery files."],
    ], [1.12, 5.82])
    _p(doc, "The Git bundle contains six commits in this order. Clone it to inspect the actual changes between stages. The shared repository link is pending and is needed for submission.")

    _heading(doc, "8. Project Management and Learning", 1)
    _p(doc, "The objective was to understand the old program, implement the two maintenance requests, refactor borrowing and prepare evidence of the result. The Git stages track when work was recorded. The software resources were the legacy Python code, the course handout, SQLite, DuckDB, Git and Radon. The diagrams, report and presentation use diagrams.net, Word and PowerPoint.")
    _table(doc, ["Milestone", "Evidence or next action", "Status"], [
        ["1–2: Analysis", "Rules, initial architecture and impact analysis", "Recorded in 01–02"],
        ["3–5: Implementation", "Maintenance, refactoring and equipment reuse", "Recorded in 03–05"],
        ["6: Validation", "Both engines, regression checks and package", "Locally verified"],
        ["Team review", "Assign owners, verify contributions and rehearse Q&A", "Planned by 21 November"],
        ["Delivery", "Share repository link and submit ZIP in Teams", "Due 22 November, 11:59 PM"],
    ], [1.53, 3.50, 1.91])
    _p(doc, "The old source could not run directly, so we separated the syntax repair. Stock and loan records could get out of step, so we tested transaction rollback and competing requests. With no source database, we created fixtures and checked migration on those. Each remaining task needs an assigned team member and a record of when it was done.")
    _p(doc, "The group record should identify the date and attendance, which idea or solution each member contributed, the communication tool, what feedback was exchanged and the decision or follow-up. This evidence and individual task ownership are pending team input.")
    _p(doc, "The final review should match the running package to the Word report, opening each figure, checking the repository link and replaying the demonstration. The reviewer can record the result beside each item in the delivery checklist for the submitter.")
    _p(doc, "The technical gaps were transaction handling, extracting behavior from a long function and measuring complexity. The SQLite and DuckDB documentation informed the storage adapters [5], [6]. Fowler's refactoring examples informed the named checks and smaller responsibilities [4]. Radon documentation helped separate the change in code size from the change in complexity [7]. During discussion, each member should be ready to explain these choices and show the terminal output.")

    _heading(doc, "9. Conclusion", 1)
    _p(doc, "The updated console program keeps the original book rules, supports more than one copy and runs with either database engine. Splitting console input, lending rules and storage made the system easier to change and enabled equipment reuse. The final evidence includes the measurements, ordered Git history and a recorded demo. Team records, the shared repository link and Teams submission remain to be completed.")

    stop = len(doc.element.body) - 1
    # Only Word text elements count, including table cells and in-line code.
    body_text = " ".join(
        t.text or "" for child in list(doc.element.body)[start:stop] for t in child.iter(qn("w:t"))
    )
    word_count = len(re.findall(r"\b[\w’'-]+\b", body_text))

    _heading(doc, "References", 1)
    for reference in (
        "[1] University of Prince Mugrin, SE431 Software Maintenance and Evolution: Fall 2026 Project Description, course handout, pp. 1–7.",
        "[2] Legacy Library System (~100 LOC), supplied Python source.",
        "[3] IEEE Computer Society, Guide to the Software Engineering Body of Knowledge, v4.0a, ch. 7, sec. 1.6, 2025. https://ieeecs-media.computer.org/media/education/swebok/swebok-v4.pdf",
        "[4] M. Fowler, Refactoring: Improving the Design of Existing Code, 2nd ed., Addison-Wesley, 2018. https://martinfowler.com/books/refactoring.html",
        "[5] SQLite, Transaction. https://www.sqlite.org/lang_transaction.html",
        "[6] DuckDB, Python DB API. https://duckdb.org/docs/stable/clients/python/dbapi.html",
        "[7] S. S. Delaney, Radon Documentation, v6.0.1. https://radon.readthedocs.io/en/latest/",
        "[8] E. J. Chikofsky and J. H. Cross II, Reverse engineering and design recovery: A taxonomy, IEEE Software, vol. 7, no. 1, 1990. doi:10.1109/52.43044.",
    ):
        p = _p(doc, reference)
        p.paragraph_format.left_indent = Inches(0.18)
        p.paragraph_format.first_line_indent = Inches(-0.18)

    _heading(doc, "Appendix A: Run and Submission Details", 1)
    _p(doc, "From Source_Code, run the command below for the SQLite book system.")
    _p(doc, "`python -m library_system --engine sqlite --database ../runtime/library.sqlite3`")
    _p(doc, "Use `--engine duckdb` with a separate database path for DuckDB. Add `--item-type equipment` for the equipment demonstration. The root README has installation, run and migration instructions.")
    _p(doc, "Shared Git repository: [add the team repository URL before submission]. The local history can be cloned from Git/SE431-project.bundle.")
    _p(doc, "Team contribution record: [date, participants, contribution, communication tool, feedback and follow-up]. Add the task owner and completion date for each actual handoff.")

    diagrams = ROOT / "Drawio_Diagrams"
    figures = (
        ("B.1 Current Architecture", "The five functions and tables in the original Python program.", "Current_Architecture_Readable"),
        ("B.2 Multiple Copies", "The three borrow requests and one return in the SQLite walkthrough.", "Multiple_Copies_Design"),
        ("B.3 Final Architecture", "The terminal uses one lending service with a choice of two repositories.", "Reengineered_Architecture"),
        ("B.4 Reusable Domain", "Books and equipment use the same operations with separate policies.", "Reusable_Domain_Architecture"),
    )
    for number, (title, caption, stem) in enumerate(figures, start=1):
        _add_landscape_figure(doc, title, caption, number, diagrams / f"{stem}.png")

    doc.core_properties.title = "SE431 Legacy Library System: Final Project Report"
    doc.core_properties.subject = "Software maintenance, refactoring and reengineering"
    doc.core_properties.author = "SE431 Project Team"
    doc.save(OUT)
    print(f"Saved {OUT}. Main report word count, including tables: {word_count}")


if __name__ == "__main__":
    build()


