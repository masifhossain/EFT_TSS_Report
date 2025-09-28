import csv
import os
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Dict, Optional

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image


@dataclass
class Record:
    tag: str  # 'D', 'S', or 'T'
    reference: str
    date: date
    time: str
    description: str
    payment_total: Optional[float]
    taxi_total: Optional[float]
    shift_total: Optional[float]
    charge: Optional[float]
    eftpos: Optional[float]
    ihail: Optional[float]
    eticket: Optional[float]
    tss: Optional[float] = None


def _parse_float(val: str) -> Optional[float]:
    v = (val or "").strip()
    if v == "" or v.lower() in {"nan", "null"}:
        return None
    # Normalize numeric strings: remove commas and non-numeric symbols (e.g., $)
    import re
    v = v.replace(",", "")
    v = "".join(re.findall(r"[-\d.]", v))
    if v in ("", "-", ".", "-."):
        return None
    try:
        return float(v)
    except ValueError:
        return None

def _date_from_filename(path: str) -> Optional[date]:
    """Try to extract a YYYYMMDD date from the CSV filename and return it as a date object."""
    try:
        base = os.path.basename(path)
        import re
        m = re.search(r"(20\d{6})", base)  # e.g., 20250915
        if m:
            return datetime.strptime(m.group(1), "%Y%m%d").date()
    except Exception:
        pass
    return None


def parse_csv_files_grouped_by_taxi(filepaths: List[str], period_start: date, period_end: date):
    """
    Parse CSV files and group records by taxi.

    Behavior:
    - Includes ALL available data for each taxi from the CSV files (no filtering by period).
      The provided period_start/period_end are used only for display in the report header.
    - Aggregates Taxi Total (T rows) across all CSVs per taxi and appends one synthetic 'T'
      record per taxi (used to compute the report's Total).

    Returns a tuple: (records_by_taxi, taxi_total_sum_by_taxi)
    - records_by_taxi: Dict[str, List[Record]] for D and S rows (all dates) plus one synthetic T row
    - taxi_total_sum_by_taxi: Dict[str, float] sum of TaxiTotal values from T rows across all CSVs
    """
    taxis: Dict[str, List[Record]] = {}
    taxi_total_sums: Dict[str, float] = {}

    for path in filepaths:
        # Collect T rows per taxi while reading file; aggregate across all files
        file_t_totals: Dict[str, float] = {}
        file_date = _date_from_filename(path)

        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header_map: Optional[Dict[str, int]] = None
            current_taxi: Optional[str] = None

            import re
            def norm(s: str) -> str:
                # Lowercase and remove all non-alphanumeric characters (handles NBSP, $ etc.)
                return re.sub(r"[^a-z0-9]", "", (s or "").lower())

            def find_index(cols_map: Dict[str, int], candidates: list[str]) -> Optional[int]:
                for key in candidates:
                    k = norm(key)
                    if k in cols_map:
                        return cols_map[k]
                return None

            for row in reader:
                if not row:
                    continue

                # Detect header row dynamically (supports schemas with/without 'Tag')
                if header_map is None:
                    cols = {norm(c): i for i, c in enumerate(row)}
                    # Consider it a header if we can find at least date and description-like columns
                    if ('date' in cols) and ('description' in cols or 'desc' in cols):
                        header_map = cols
                        continue
                    # If not a header, keep reading until we find one or process as data using default positions
                    # Fall through to attempt default Tag schema

                # Helper to get index by normalized name
                def idx(names: list[str]) -> Optional[int]:
                    if header_map is None:
                        return None
                    return find_index(header_map, names)

                # Try to read fields using header when available; else fallback to Tag schema positions
                tag_val = None
                taxi = ''
                reference = ''
                date_str = ''
                time_str = ''
                description = ''
                payment_total = None
                taxi_total = None
                shift_total = None
                charge = None
                eftpos = None
                ihail = None
                eticket = None
                tss = None

                if header_map is not None:
                    itag = idx(['tag'])
                    itaxi = idx(['taxi','taxinumber','taxino','taxi#'])
                    iref = idx(['reference','ref','refno'])
                    idate = idx(['date','trandate','txndate'])
                    itime = idx(['time','trantime','txntime'])
                    idesc = idx(['description','desc'])
                    ipay = idx(['paymenttotal','payment','totalpayment'])
                    itaxi_tot = idx(['taxitotal','taxi total','$taxitotal','taxitotal$'])
                    ishift_tot = idx(['shifttotal'])
                    icharge = idx(['charge'])
                    ieftpos = idx(['eftpos'])
                    iihail = idx(['ihail','ihailtotal'])
                    ieticket = idx(['eticket','etickettotal'])
                    itss = idx(['tss','tss($)','tsstotal'])

                    tag_val = (row[itag].strip() if itag is not None and itag < len(row) else '')
                    taxi = (row[itaxi].strip() if itaxi is not None and itaxi < len(row) else '')
                    reference = (row[iref].strip() if iref is not None and iref < len(row) else '')
                    date_str = (row[idate].strip() if idate is not None and idate < len(row) else '')
                    time_str = (row[itime].strip() if itime is not None and itime < len(row) else '')
                    description = (row[idesc].strip() if idesc is not None and idesc < len(row) else '')
                    payment_total = _parse_float(row[ipay]) if ipay is not None and ipay < len(row) else None
                    taxi_total = _parse_float(row[itaxi_tot]) if itaxi_tot is not None and itaxi_tot < len(row) else None
                    shift_total = _parse_float(row[ishift_tot]) if ishift_tot is not None and ishift_tot < len(row) else None
                    charge = _parse_float(row[icharge]) if icharge is not None and icharge < len(row) else None
                    eftpos = _parse_float(row[ieftpos]) if ieftpos is not None and ieftpos < len(row) else None
                    ihail = _parse_float(row[iihail]) if iihail is not None and iihail < len(row) else None
                    eticket = _parse_float(row[ieticket]) if ieticket is not None and ieticket < len(row) else None
                    tss = _parse_float(row[itss]) if itss is not None and itss < len(row) else None
                else:
                    # Fallback to Tag schema positions
                    tag_val = row[0].strip() if len(row) > 0 else ''
                    taxi = row[2].strip() if len(row) > 2 else ''
                    reference = row[5].strip() if len(row) > 5 else ''
                    date_str = row[6].strip() if len(row) > 6 else ''
                    time_str = row[7].strip() if len(row) > 7 else ''
                    description = row[8].strip() if len(row) > 8 else ''
                    payment_total = _parse_float(row[9]) if len(row) > 9 else None
                    taxi_total = _parse_float(row[10]) if len(row) > 10 else None
                    shift_total = _parse_float(row[11]) if len(row) > 11 else None
                    # Many files place TSS at column M (index 12). Prefer mapping it here.
                    tss = _parse_float(row[12]) if len(row) > 12 else None
                    charge = _parse_float(row[13]) if len(row) > 13 else None
                    eftpos = _parse_float(row[14]) if len(row) > 14 else None
                    ihail = _parse_float(row[15]) if len(row) > 15 else None
                    eticket = _parse_float(row[16]) if len(row) > 16 else None

                # Determine row type
                row_desc_norm = norm(description)
                if tag_val in {'T', 'S', 'D'}:
                    row_type = tag_val
                else:
                    if row_desc_norm == 'taxitotal':
                        row_type = 'T'
                    elif row_desc_norm == 'shifttotal':
                        row_type = 'S'
                    else:
                        row_type = 'D'

                # Choose a stable taxi id for grouping and filenames
                import re as _re
                def looks_like_date(s: str) -> bool:
                    return bool(_re.match(r"^\d{1,2}[-/ ]\d{1,2}[-/ ]\d{2,4}$", (s or "").strip()))

                def valid_taxi_text(s: str) -> bool:
                    s = (s or '').strip()
                    if s == '':
                        return False
                    if looks_like_date(s):
                        return False
                    # Accept alphanumeric like TX68, TC396, etc., or pure numbers with length >= 3
                    if _re.match(r'^[A-Za-z]+\d+$', s):
                        return True
                    if _re.match(r'^\d{3,}$', s):
                        return True
                    return False

                if valid_taxi_text(taxi):
                    current_taxi = taxi
                taxi_key = current_taxi if valid_taxi_text(current_taxi or '') else ('UNKNOWN')

                # Parse date
                rec_date = None
                if date_str:
                    try:
                        rec_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                    except Exception:
                        rec_date = None
                if rec_date is None:
                    rec_date = file_date or period_start

                if row_type == 'T':
                    if taxi_key:
                        file_t_totals[taxi_key] = file_t_totals.get(taxi_key, 0.0) + (taxi_total or 0.0)
                        rec = Record(
                            tag='T',
                            reference='',
                            date=rec_date,
                            time='',
                            description='TaxiTotal',
                            payment_total=None,
                            taxi_total=taxi_total,
                            shift_total=None,
                            charge=None,
                            eftpos=None,
                            ihail=None,
                            eticket=None,
                            tss=None,
                        )
                        taxis.setdefault(taxi_key, []).append(rec)
                    continue

                if row_type == 'S':
                    rec = Record(
                        tag='S',
                        reference=reference,
                        date=rec_date,
                        time=time_str,
                        description=description,
                        payment_total=None,
                        taxi_total=None,
                        shift_total=shift_total,
                        charge=None,
                        eftpos=None,
                        ihail=None,
                        eticket=None,
                        tss=None,
                    )
                    taxis.setdefault(taxi_key, []).append(rec)
                    continue

                # D row
                rec = Record(
                    tag='D',
                    reference=reference,
                    date=rec_date,
                    time=time_str,
                    description=description,
                    payment_total=payment_total,
                    taxi_total=taxi_total,
                    shift_total=shift_total,
                    charge=charge,
                    eftpos=eftpos,
                    ihail=ihail,
                    eticket=eticket,
                    tss=tss,
                )

                taxis.setdefault(taxi_key, []).append(rec)

        # Aggregate taxi totals across files
        for taxi, t_total in file_t_totals.items():
            taxi_total_sums[taxi] = taxi_total_sums.get(taxi, 0.0) + (t_total or 0.0)

    # Note: We do not append an extra synthetic T record here to avoid duplicating totals in the detail table.

    # sort each taxi's records by date/time
    for taxi, records in taxis.items():
        def time_key(r: Record):
            try:
                t = datetime.strptime(r.time, "%H:%M:%S").time()
            except Exception:
                t = datetime.min.time()
            return (r.date, t)

        records.sort(key=time_key)

    return taxis, taxi_total_sums


def _money(v: Optional[float]) -> str:
    return f"{v:,.2f}" if isinstance(v, (int, float)) and v is not None else ""


def generate_pdf_for_taxi(
    taxi: str,
    records: List[Record],
    period_start: date,
    period_end: date,
    date_issued: date,
    output_path: str,
    static_folder: str,
):
    # Prefer total from T records if present; otherwise sum D rows' taxi_total
    t_totals = [r.taxi_total or 0.0 for r in records if r.tag == 'T']
    if t_totals:
        total_taxi_total = sum(t_totals)
    else:
        total_taxi_total = sum((r.taxi_total or 0.0) for r in records if r.tag == 'D')

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    # Header layout: left (logo + ABN + title), right (Taxi number / Date issued / Total)
    logo_path = os.path.join(static_folder, "logo.png")
    left_cells = []
    if os.path.exists(logo_path):
        img = Image(logo_path)
        img._restrictSize(45 * mm, 22 * mm)
        left_cells.append(img)
        left_cells.append(Spacer(1, 2 * mm))
    left_cells.append(Paragraph("ABN 95 610 943 934", styles['Normal']))
    left_cells.append(Spacer(1, 2 * mm))
    # Slightly smaller than 'Title' to avoid overly large heading
    left_cells.append(Paragraph("Taxi EFTPOS Statement", styles['Heading2']))

    # Right-side info table (labels and values)
    label_style = ParagraphStyle(
        name='RightLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
    )
    value_style = styles['Normal']
    date_issued_text = date_issued.strftime('%d-%b-%Y')
    right_data = [
        [Paragraph('Taxi number', label_style), Paragraph(taxi, value_style)],
        [Paragraph('Date issued', label_style), Paragraph(date_issued_text, value_style)],
        [Paragraph('Total', label_style), Paragraph(f"{_money(total_taxi_total)}", value_style)],
    ]
    right_table = Table(right_data, colWidths=[35 * mm, None])
    right_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    # Combine left and right into header table
    header = Table([[left_cells, right_table]], colWidths=[None, 70 * mm])
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    story.append(header)
    story.append(Spacer(1, 6 * mm))

    # Period line: "Monday dd/mm/yyyy - Sunday dd/mm/yyyy"
    period_text = f"{period_start.strftime('%A %d/%m/%Y')} - {period_end.strftime('%A %d/%m/%Y')}"
    story.append(Paragraph(period_text, styles['Normal']))
    story.append(Spacer(1, 6 * mm))

    # Table header
    data = [[
        "Reference",
        "Date",
        "Time",
        "Description",
        "Taxi Total ($)",
        "Shift Total ($)",
        "Charge ($)",
        "EFTPOS ($)",
        "iHail",
        "Eticket ($)",
    ]]

    # Group by date and write rows per date, then append a bold 'Taxi Total (dd/mm/yyyy)' summary row
    from collections import defaultdict
    by_date = defaultdict(list)
    for r in records:
        if r.tag == 'T':
            # We'll add a summary for Taxi Total at the end of this date group
            by_date[r.date].append(r)
        else:
            by_date[r.date].append(r)

    # Define a style for summary rows (bold)
    summary_rows = []  # collect indexes to style later
    for day in sorted(by_date.keys()):
        t_values = []
        for r in by_date[day]:
            if r.tag == 'T':
                t_values.append(r.taxi_total or 0.0)
                continue
            data.append([
                r.reference,
                r.date.strftime('%d/%m/%Y'),
                r.time,
                r.description,
                _money(r.taxi_total),
                _money(r.shift_total),
                _money(r.charge),
                _money(r.eftpos),
                _money(r.ihail),
                _money(r.eticket),
            ])
        # Append the Taxi Total summary for this day, if any T values present
        if t_values:
            total_for_day = sum(t_values)
            row = [
                '',
                day.strftime('%d/%m/%Y'),  # Date column shows the date of the Taxi Total
                '',
                'TaxiTotal',  # Description column fixed text
                _money(total_for_day),
                '',
                '',
                '',
                '',
                '',
            ]
            data.append(row)
            summary_rows.append(len(data) - 1)

    table = Table(data, repeatRows=1)
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (-6, 1), (-1, -1), 'RIGHT'),  # right-align numeric columns
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.aliceblue]),
    ])
    # Make summary rows bold
    for r_idx in summary_rows:
        table_style.add('FONTNAME', (0, r_idx), (-1, r_idx), 'Helvetica-Bold')
        table_style.add('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor('#f5f5f5'))
    table.setStyle(table_style)

    story.append(table)

    doc.build(story)


def generate_pdf_for_taxi_tss(
    taxi: str,
    records: List[Record],
    period_start: date,
    period_end: date,
    date_issued: date,
    output_path: str,
    static_folder: str,
):
    # Sum TSS across D rows; if none present, fall back to Taxi Totals
    tss_values = [r.tss for r in records if r.tag == 'D' and r.tss is not None]
    if tss_values:
        total_value = sum(tss_values)
    else:
        total_value = sum((r.taxi_total or 0.0) for r in records if r.tag in {'T', 'D'})

    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    # Header
    logo_path = os.path.join(static_folder, "logo.png")
    left_cells = []
    if os.path.exists(logo_path):
        img = Image(logo_path)
        img._restrictSize(45 * mm, 22 * mm)
        left_cells.append(img)
        left_cells.append(Spacer(1, 2 * mm))
    left_cells.append(Paragraph("ABN 95 610 943 934", styles['Normal']))
    left_cells.append(Spacer(1, 2 * mm))
    left_cells.append(Paragraph("Taxi TSS Statement", styles['Heading2']))

    label_style = ParagraphStyle(
        name='RightLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
    )
    value_style = styles['Normal']
    date_issued_text = date_issued.strftime('%d-%b-%Y')
    right_data = [
        [Paragraph('Taxi number', label_style), Paragraph(taxi, value_style)],
        [Paragraph('Date issued', label_style), Paragraph(date_issued_text, value_style)],
        [Paragraph('Total', label_style), Paragraph(f"{_money(total_value)}", value_style)],
    ]
    right_table = Table(right_data, colWidths=[35 * mm, None])
    right_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    header = Table([[left_cells, right_table]], colWidths=[None, 70 * mm])
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    story.append(header)
    story.append(Spacer(1, 6 * mm))

    period_text = f"{period_start.strftime('%A %d/%m/%Y')} - {period_end.strftime('%A %d/%m/%Y')}"
    story.append(Paragraph(period_text, styles['Normal']))
    story.append(Spacer(1, 6 * mm))

    # Columns required for TSS report (Taxi Total not required)
    data = [[
        "Reference",
        "Date",
        "Time",
        "Description",
        "Shift Total ($)",
        "TSS ($)",
    ]]

    from collections import defaultdict
    by_date = defaultdict(list)
    for r in records:
        by_date[r.date].append(r)

    for day in sorted(by_date.keys()):
        for r in by_date[day]:
            if r.tag == 'T':
                # Skip TaxiTotal rows in TSS report
                continue
            data.append([
                r.reference,
                r.date.strftime('%d/%m/%Y'),
                r.time,
                r.description,
                _money(r.shift_total),
                _money(r.tss),
            ])

    table = Table(data, repeatRows=1)
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (-2, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.aliceblue]),
    ])
    table.setStyle(table_style)

    story.append(table)

    doc.build(story)
