from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

HEADERS = ["ت", "اسم الموظف", "رقم الموظف", "التاريخ", "اليوم", "الوقت", "الجهاز"]
WIDTHS = [8, 28, 16, 16, 16, 16, 24]

NAVY = "1D4ED8"
INK = "0F172A"
MUTED = "475569"
LINE = "E2E8F0"
ZEBRA = "F8FAFC"
HEADER_BG = "1D4ED8"
thin = Border(
    left=Side(style="thin", color=LINE),
    right=Side(style="thin", color=LINE),
    top=Side(style="thin", color=LINE),
    bottom=Side(style="thin", color=LINE),
)
right_align = Alignment(horizontal="right", vertical="center", readingOrder=2)
center_align = Alignment(horizontal="center", vertical="center", readingOrder=2)


def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)


def _meta_line(meta):
    search = meta["query"] or "غير محدد"
    return (
        f"الجهاز: {meta['device']}  ·  "
        f"من: {meta['date_from']}  ·  "
        f"إلى: {meta['date_to']}  ·  "
        f"البحث: {search}"
    )


def build_workbook(rows, meta):
    wb = Workbook()
    ws = wb.active
    ws.title = "البصمات"
    ws.sheet_view.rightToLeft = True
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.6, bottom=0.6, header=0.2, footer=0.2)
    ws.print_title_rows = "1:4"
    ws.oddFooter.center.text = "صفحة &P من &N"
    ws.sheet_properties.tabColor = NAVY

    last_col = get_column_letter(len(HEADERS))
    ws.merge_cells(f"A1:{last_col}1")
    ws.merge_cells(f"A2:{last_col}2")
    ws.merge_cells(f"A3:{last_col}3")

    title = ws["A1"]
    title.value = "تقرير بصمات الموظفين"
    title.font = Font(name="Arial", size=18, bold=True, color=INK)
    title.alignment = right_align

    summary = ws["A2"]
    summary.value = f"تاريخ التصدير: {meta['exported_at']}    ·    عدد السجلات: {meta['count']}"
    summary.font = Font(name="Arial", size=11, color=MUTED)
    summary.alignment = right_align

    filters = ws["A3"]
    filters.value = _meta_line(meta)
    filters.font = Font(name="Arial", size=11, color=MUTED)
    filters.alignment = right_align

    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 20

    for index, header in enumerate(HEADERS, start=1):
        cell = ws.cell(4, index, header)
        cell.font = Font(name="Arial", size=12, bold=True, color="FFFFFF")
        cell.fill = _fill(HEADER_BG)
        cell.alignment = center_align
        cell.border = thin
    ws.row_dimensions[4].height = 24
    last_row = 4 + len(rows)
    ws.auto_filter.ref = f"A4:{last_col}{last_row}"
    ws.freeze_panes = "A5"

    for offset, row in enumerate(rows, start=1):
        excel_row = 4 + offset
        values = [
            offset,
            row["employee_name"] or "—",
            row["user_id"],
            row["date"],
            row["weekday"],
            row["time"],
            row["device_name"],
        ]
        zebra = offset % 2 == 0
        for index, value in enumerate(values, start=1):
            cell = ws.cell(excel_row, index, value)
            cell.font = Font(name="Arial", size=11, color=INK)
            cell.border = thin
            cell.alignment = center_align if index in (1, 3, 4, 5, 6) else right_align
            if zebra:
                cell.fill = _fill(ZEBRA)
        ws.row_dimensions[excel_row].height = 22

    for index, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width

    ws.page_setup.horizontalCentered = True
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_summary_workbook(sheet_title, title_text, headers, widths, rows, meta):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.sheet_view.rightToLeft = True
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.6, bottom=0.6, header=0.2, footer=0.2)
    ws.print_title_rows = "1:4"
    ws.oddFooter.center.text = "صفحة &P من &N"
    ws.sheet_properties.tabColor = NAVY

    last_col = get_column_letter(len(headers))
    ws.merge_cells(f"A1:{last_col}1")
    ws.merge_cells(f"A2:{last_col}2")
    ws.merge_cells(f"A3:{last_col}3")

    title = ws["A1"]
    title.value = title_text
    title.font = Font(name="Arial", size=18, bold=True, color=INK)
    title.alignment = right_align

    summary = ws["A2"]
    summary.value = f"تاريخ التصدير: {meta['exported_at']}    ·    عدد السجلات: {meta['count']}"
    summary.font = Font(name="Arial", size=11, color=MUTED)
    summary.alignment = right_align

    filters = ws["A3"]
    filters.value = meta["line"]
    filters.font = Font(name="Arial", size=11, color=MUTED)
    filters.alignment = right_align

    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 20

    for index, header in enumerate(headers, start=1):
        cell = ws.cell(4, index, header)
        cell.font = Font(name="Arial", size=12, bold=True, color="FFFFFF")
        cell.fill = _fill(HEADER_BG)
        cell.alignment = center_align
        cell.border = thin
    ws.row_dimensions[4].height = 24
    last_row = 4 + len(rows)
    ws.auto_filter.ref = f"A4:{last_col}{max(last_row, 4)}"
    ws.freeze_panes = "A5"

    for offset, values in enumerate(rows, start=1):
        excel_row = 4 + offset
        zebra = offset % 2 == 0
        for index, value in enumerate(values, start=1):
            cell = ws.cell(excel_row, index, value)
            cell.font = Font(name="Arial", size=11, color=INK)
            cell.border = thin
            cell.alignment = right_align if index == 2 else center_align
            if zebra:
                cell.fill = _fill(ZEBRA)
        ws.row_dimensions[excel_row].height = 22

    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
