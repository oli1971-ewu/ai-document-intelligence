# Sample Test Documents

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
