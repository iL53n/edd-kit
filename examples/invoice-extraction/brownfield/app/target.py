"""Offline invoice extraction for the explicitly scoped synthetic feature."""

import json
import re
import sys
from decimal import Decimal


def extract_invoice(source):
    fields = {}
    for line in source.splitlines():
        label, separator, value = line.partition(":")
        if separator:
            fields.setdefault(label.strip(), set()).add(value.strip())
    fields = {label: next(iter(values)) for label, values in fields.items() if len(values) == 1}
    currency = fields.get("Currency")
    if currency not in {"USD", "EUR"}:
        currency = None
    amount = fields.get("Total", "")
    total = (
        format(Decimal(amount), ".2f")
        if re.fullmatch(r"-?[0-9]+(?:\.[0-9]{1,2})?", amount)
        else None
    )
    return {"currency": currency, "total": total}


if __name__ == "__main__":
    request = json.load(sys.stdin)
    print(json.dumps({"actual_output": json.dumps(extract_invoice(request["input"]))}))
