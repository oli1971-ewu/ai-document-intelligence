"""
Evaluation script for Doc Intel.
Runs end-to-end evaluation on benchmark/sample documents and computes:
- Pipeline success rate
- Information extraction accuracy (precision, recall, field-level accuracy)
- Processing time & latency benchmarks
- Validation issue detection rate
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from decimal import Decimal
from unittest.mock import MagicMock

# Setup path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.processing.pipeline import process_document
from app.services.extraction.extractor import extract_invoice
from app.services.validation.validator import _run_rules


SAMPLES_DIR = BACKEND_DIR.parent / "samples"

# Labeled Ground Truth for evaluation
BENCHMARK_CASES = [
    {
        "file": "sample_invoice_1.pdf",
        "doc_type": "pdf",
        "expected_fields": {
            "invoice_number": "INV-2024-0042",
            "invoice_date": "2024-03-15",
            "currency": "USD",
            "subtotal": 6000.0,
            "tax": 1200.0,
            "total": 7200.0,
        },
        "expected_validation_errors": 0,
    },
    {
        "file": "sample_invoice_2_math_error.pdf",
        "doc_type": "pdf",
        "expected_fields": {
            "invoice_number": "INV-DUPE-0001",
            "invoice_date": "15/03/2024",
            "currency": "EUR",
            "subtotal": 2500.0,
            "tax": 525.0,
            "total": 2900.0,  # Intentional error: 2500 + 525 = 3025 != 2900
        },
        "expected_validation_issues": ["TOTAL_MISMATCH"],
    },
    {
        "file": "sample_invoices.csv",
        "doc_type": "csv",
        "expected_fields": {
            "contains_text": "INV-CSV-001",
        },
        "expected_validation_errors": 0,
    },
    {
        "file": "sample_invoices.xlsx",
        "doc_type": "xlsx",
        "expected_fields": {
            "contains_text": "INV-XL-001",
        },
        "expected_validation_errors": 0,
    },
]


def run_evaluation() -> dict:
    print("=" * 65)
    print("      DOC INTEL PIPELINE & ACCURACY EVALUATION BENCHMARK      ")
    print("=" * 65)

    total_docs = len(BENCHMARK_CASES)
    succeeded_docs = 0
    processing_times = []
    field_evaluations = {"correct": 0, "total": 0}
    validation_evaluations = {"detected": 0, "expected": 0}

    print(f"\n[1] Running Pipeline Evaluation on {total_docs} Benchmark Documents...\n")

    for case in BENCHMARK_CASES:
        filepath = SAMPLES_DIR / case["file"]
        if not filepath.exists():
            print(f"  [MISSING] {case['file']} not found in samples directory.")
            continue

        start_time = time.perf_counter()
        result = process_document(str(filepath))
        duration_ms = (time.perf_counter() - start_time) * 1000
        processing_times.append(duration_ms)

        if result.success:
            succeeded_docs += 1
            status_str = f"SUCCESS ({duration_ms:.1f}ms)"
        else:
            status_str = f"FAILED: {result.error}"

        print(f"  - {case['file']:<35} | Type: {result.doc_type:<5} | Status: {status_str}")

        # Evaluate text or field extractions
        if result.success and "contains_text" in case["expected_fields"]:
            field_evaluations["total"] += 1
            if case["expected_fields"]["contains_text"] in result.text:
                field_evaluations["correct"] += 1

        if result.success and case["doc_type"] == "pdf":
            inv = extract_invoice(result.text)
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            issues = _run_rules(inv, mock_db, uuid.uuid4())
            detected_codes = [i["code"] for i in issues]

            for field, exp_val in case["expected_fields"].items():
                field_evaluations["total"] += 1
                actual_val = getattr(inv, field, None)
                if actual_val == exp_val:
                    field_evaluations["correct"] += 1
                else:
                    print(f"      Mismatch on {field}: expected '{exp_val}', got '{actual_val}'")

            # Validation checks
            expected_issues = case.get("expected_validation_issues", [])
            for exp_code in expected_issues:
                validation_evaluations["expected"] += 1
                if exp_code in detected_codes:
                    validation_evaluations["detected"] += 1
                else:
                    print(f"      Expected validation issue '{exp_code}' was not detected!")

    success_rate = (succeeded_docs / total_docs * 100) if total_docs > 0 else 0
    accuracy_rate = (
        (field_evaluations["correct"] / field_evaluations["total"] * 100)
        if field_evaluations["total"] > 0
        else 0
    )
    validation_rate = (
        (validation_evaluations["detected"] / validation_evaluations["expected"] * 100)
        if validation_evaluations["expected"] > 0
        else 100.0
    )
    avg_latency = sum(processing_times) / len(processing_times) if processing_times else 0

    print("\n" + "=" * 65)
    print("                     EVALUATION SUMMARY                        ")
    print("=" * 65)
    print(f"  Total Processed Documents      : {total_docs}")
    print(f"  Pipeline Success Rate          : {success_rate:.1f}% ({succeeded_docs}/{total_docs})")
    print(f"  Field Extraction Accuracy      : {accuracy_rate:.1f}% ({field_evaluations['correct']}/{field_evaluations['total']})")
    print(f"  Validation Rule Detection Rate : {validation_rate:.1f}% ({validation_evaluations['detected']}/{validation_evaluations['expected']})")
    print(f"  Average Processing Latency     : {avg_latency:.2f} ms")
    print(f"  Min / Max Processing Latency   : {min(processing_times):.2f} ms / {max(processing_times):.2f} ms")
    print("=" * 65 + "\n")

    return {
        "total_docs": total_docs,
        "succeeded_docs": succeeded_docs,
        "success_rate": success_rate,
        "accuracy_rate": accuracy_rate,
        "validation_rate": validation_rate,
        "avg_latency_ms": avg_latency,
    }


if __name__ == "__main__":
    run_evaluation()
