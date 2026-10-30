"""
Generate sample invoice documents for testing:
  - sample_invoice_1.pdf  (digital PDF with all fields)
  - sample_invoice_2.pdf  (PDF with math mismatch for validation testing)
  - sample_invoice.csv    (CSV with multiple invoices)
  - sample_invoice.xlsx   (Excel spreadsheet)
  - README.md             (describes each sample)

Run from project root: python samples/generate_samples.py
"""
import os
import csv

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


SAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))


def make_pdf_1():
    """Well-formed invoice — all fields present, math correct."""
    if not HAS_REPORTLAB:
        print("reportlab not installed, skipping PDF generation")
        return
    path = os.path.join(SAMPLES_DIR, "sample_invoice_1.pdf")
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter

    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, h - 60, "INVOICE")

    c.setFont("Helvetica", 11)
    lines = [
        ("Invoice No:", "INV-2024-0042"),
        ("Invoice Date:", "2024-03-15"),
        ("Due Date:", "2024-04-15"),
        ("Supplier:", "Acme Supplies Ltd, 123 Business Park, London UK"),
        ("Customer:", "Tech Corp International, 456 Corporate Ave, New York USA"),
    ]
    y = h - 110
    for label, value in lines:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, label)
        c.setFont("Helvetica", 10)
        c.drawString(200, y, value)
        y -= 20

    # Line items header
    y -= 20
    c.setFont("Helvetica-Bold", 10)
    for col, x in [("Description", 50), ("Qty", 300), ("Unit Price", 360), ("Amount", 450)]:
        c.drawString(x, y, col)
    y -= 5
    c.line(50, y, 550, y)
    y -= 15

    items = [
        ("Web Development Services", 1, 5000.00, 5000.00),
        ("Cloud Hosting (Monthly)", 3, 200.00, 600.00),
        ("Support Package", 1, 400.00, 400.00),
    ]
    c.setFont("Helvetica", 10)
    for desc, qty, unit, amt in items:
        c.drawString(50, y, desc)
        c.drawString(300, y, str(qty))
        c.drawString(360, y, f"${unit:,.2f}")
        c.drawString(450, y, f"${amt:,.2f}")
        y -= 18

    y -= 10
    c.line(350, y, 550, y)
    y -= 15
    totals = [("Subtotal:", "$6,000.00"), ("Tax (20%):", "$1,200.00"), ("TOTAL:", "$7,200.00")]
    for label, val in totals:
        c.setFont("Helvetica-Bold" if label == "TOTAL:" else "Helvetica", 10)
        c.drawString(360, y, label)
        c.drawString(450, y, val)
        y -= 15

    c.setFont("Helvetica", 9)
    c.drawString(50, 50, "Currency: USD  |  Payment terms: Net 30  |  Thank you for your business!")
    c.save()
    print(f"Created {path}")


def make_pdf_2():
    """Invoice with a math error (subtotal + tax ≠ total) to test validation."""
    if not HAS_REPORTLAB:
        return
    path = os.path.join(SAMPLES_DIR, "sample_invoice_2_math_error.pdf")
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter

    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, h - 60, "INVOICE")

    c.setFont("Helvetica", 11)
    y = h - 110
    for label, value in [
        ("Invoice No:", "INV-DUPE-0001"),
        ("Invoice Date:", "15/03/2024"),
        ("Supplier:", "Globex Corporation"),
        ("Customer:", "Springfield Power Plant"),
    ]:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, label)
        c.setFont("Helvetica", 10)
        c.drawString(200, y, value)
        y -= 20

    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(360, y, "Subtotal:")
    c.drawString(450, y, "€2,500.00")
    y -= 15
    c.drawString(360, y, "VAT (21%):")
    c.drawString(450, y, "€525.00")
    y -= 15
    c.setFont("Helvetica-Bold", 10)
    c.drawString(360, y, "TOTAL:")
    c.drawString(450, y, "€2,900.00")  # Wrong! Should be 3025.00

    c.setFont("Helvetica", 9)
    c.drawString(50, 50, "Currency: EUR")
    c.save()
    print(f"Created {path}")


def make_csv():
    path = os.path.join(SAMPLES_DIR, "sample_invoices.csv")
    rows = [
        ["invoice_number", "invoice_date", "supplier_name", "customer_name",
         "subtotal", "tax", "total", "currency", "status"],
        ["INV-CSV-001", "2024-01-10", "Alpha Tech Solutions", "Beta Corp",
         "1500.00", "225.00", "1725.00", "USD", "paid"],
        ["INV-CSV-002", "2024-01-15", "Gamma Logistics", "Delta Inc",
         "3200.00", "512.00", "3712.00", "USD", "pending"],
        ["INV-CSV-003", "2024-02-01", "Epsilon Services", "Zeta Ltd",
         "890.00", "160.20", "1050.20", "EUR", "overdue"],
        ["INV-CSV-004", "2024-02-14", "Eta Consulting", "Theta GmbH",
         "5600.00", "1008.00", "6608.00", "EUR", "paid"],
        ["INV-CSV-005", "2024-03-05", "Iota Systems", "Kappa Corp",
         "12000.00", "1200.00", "13200.00", "GBP", "pending"],
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"Created {path}")


def make_xlsx():
    if not HAS_OPENPYXL:
        print("openpyxl not installed, skipping XLSX generation")
        return
    path = os.path.join(SAMPLES_DIR, "sample_invoices.xlsx")
    wb = openpyxl.Workbook()

    # Sheet 1: Invoice list
    ws1 = wb.active
    ws1.title = "Invoices"
    headers = ["Invoice No", "Date", "Supplier", "Customer", "Subtotal", "Tax", "Total", "Currency"]
    ws1.append(headers)
    data = [
        ["INV-XL-001", "2024-01-20", "Lambda Corp", "Mu Industries", 4500.00, 810.00, 5310.00, "USD"],
        ["INV-XL-002", "2024-02-01", "Nu Technologies", "Xi Holding", 2100.00, 378.00, 2478.00, "EUR"],
        ["INV-XL-003", "2024-02-28", "Omicron Labs", "Pi Research", 7800.00, 1404.00, 9204.00, "GBP"],
    ]
    for row in data:
        ws1.append(row)

    # Sheet 2: Line items
    ws2 = wb.create_sheet("Line Items")
    ws2.append(["Invoice No", "Description", "Qty", "Unit Price", "Amount"])
    line_items = [
        ["INV-XL-001", "Software License", 5, 700.00, 3500.00],
        ["INV-XL-001", "Implementation", 1, 1000.00, 1000.00],
        ["INV-XL-002", "Consulting (hours)", 21, 100.00, 2100.00],
        ["INV-XL-003", "Hardware", 3, 2600.00, 7800.00],
    ]
    for row in line_items:
        ws2.append(row)

    wb.save(path)
    print(f"Created {path}")


def make_readme():
    path = os.path.join(SAMPLES_DIR, "README.md")
    content = """# Sample Test Documents

These files are used for testing the Doc Intel system.

| File | Type | Description | Expected Issues |
|------|------|-------------|----------------|
| sample_invoice_1.pdf | PDF (digital) | Well-formed invoice, all fields, math correct | None |
| sample_invoice_2_math_error.pdf | PDF (digital) | Invoice with subtotal+tax ≠ total | TOTAL_MISMATCH |
| sample_invoices.csv | CSV | 5 invoices in tabular format | None |
| sample_invoices.xlsx | XLSX | Multi-sheet: invoice list + line items | None |

## Expected Extraction Results

### sample_invoice_1.pdf
- Invoice No: INV-2024-0042
- Date: 2024-03-15
- Supplier: Acme Supplies Ltd
- Customer: Tech Corp International
- Subtotal: $6,000.00
- Tax: $1,200.00
- Total: $7,200.00
- Currency: USD
- Line items: 3

### sample_invoice_2_math_error.pdf
- Invoice No: INV-DUPE-0001
- Subtotal: €2,500.00
- Tax: €525.00
- Total: €2,900.00 ← **WRONG** (should be €3,025.00)
- Expected validation: TOTAL_MISMATCH error
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created {path}")


if __name__ == "__main__":
    print("Generating sample documents...")
    make_pdf_1()
    make_pdf_2()
    make_csv()
    make_xlsx()
    make_readme()
    print("Done!")
