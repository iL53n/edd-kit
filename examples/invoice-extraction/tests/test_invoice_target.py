"""Ordinary application tests at the agreed target JSON process boundary."""

import json
import subprocess
import sys
import unittest
from pathlib import Path


class InvoiceTargetTests(unittest.TestCase):
    def invoke(self, invoice):
        project = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "targets/invoice-extraction/candidate.py"],
            cwd=project,
            input=json.dumps(
                {"case_id": "ordinary-test", "input": invoice, "fixture": {}, "trial": 1}
            ),
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        envelope = json.loads(result.stdout)
        self.assertEqual(set(envelope), {"actual_output"})
        return json.loads(envelope["actual_output"])

    def test_returns_explicit_total_instead_of_subtotal(self):
        invoice = "Invoice X-908\nCurrency: EUR\nSubtotal: 17.00\nTax: 3.40\nTotal: 20.40\n"
        self.assertEqual(self.invoke(invoice), {"currency": "EUR", "total": "20.40"})

    def test_ambiguous_field_is_null_without_erasing_the_other_field(self):
        examples = (
            ("Currency: USD\nTotal: 8.00\nTotal: 9.00\n", {"currency": "USD", "total": None}),
            ("Currency: USD\nCurrency: EUR\nTotal: 9.00\n", {"currency": None, "total": "9.00"}),
        )
        for invoice, expected in examples:
            with self.subTest(invoice=invoice):
                self.assertEqual(self.invoke(invoice), expected)


if __name__ == "__main__":
    unittest.main()
