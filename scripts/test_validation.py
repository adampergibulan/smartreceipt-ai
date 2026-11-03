from bot.schemas import ReceiptData
from bot.validation import validate_receipt


def make(**overrides):
    """A good dummy receipt. Each test changes only what it needs."""
    base = {
        "is_receipt": True,
        "image_quality": "clear",
        "supplier_name": "ABC Food Supplier",
        "receipt_date": "2026-10-23",
        "receipt_date_raw": "23/10/2026",
        "receipt_number": "INV-00125",
        "items": [
            {"item_name": "Chicken Breast", "quantity": 10, "unit": "KG",
             "unit_price": 12.0, "line_total": 120.0},
            {"item_name": "Cooking Oil", "quantity": 5, "unit": "BOTTLE",
             "unit_price": 30.0, "line_total": 150.0},
        ],
        "subtotal": 270.0,
        "tax_amount": None,
        "discount_amount": None,
        "grand_total": 270.0,
        "currency": "MYR",
        "ai_notes": [],
    }
    base.update(overrides)
    return ReceiptData(**base)


bad_line_items = [
    {"item_name": "Chicken Breast", "quantity": 10, "unit": "KG",
     "unit_price": 12.0, "line_total": 100.0},
    {"item_name": "Cooking Oil", "quantity": 5, "unit": "BOTTLE",
     "unit_price": 30.0, "line_total": 150.0},
]

# (name, receipt, should it need review?)
cases = [
    ("1. Good receipt", make(), False),
    ("2. Missing supplier and receipt number", make(supplier_name=None, receipt_number=None), True),
    ("3. Grand total does not match", make(grand_total=300.0), True),
    ("4. Tax added to total (6%)", make(tax_amount=16.2, grand_total=286.2), False),
    ("5. Tax already included in total", make(tax_amount=15.28, grand_total=270.0), False),
    ("6. Rounding of 0.02", make(grand_total=270.02), False),
    ("7. Date 19/10/26 worked out by app", make(receipt_date=None, receipt_date_raw="19/10/26"), False),
    ("8. Ambiguous date 03/04/26", make(receipt_date=None, receipt_date_raw="03/04/26"), True),
    ("9. Currency not clear", make(currency=None), True),
    ("10. Line total is wrong", make(items=bad_line_items), True),
    ("11. Blurry image", make(
        image_quality="unreadable", supplier_name=None, receipt_date=None,
        receipt_date_raw=None, receipt_number=None, items=[],
        subtotal=None, grand_total=None, currency=None), True),
]

for name, receipt, expected_review in cases:
    result = validate_receipt(receipt)
    status = "PASS" if result.review_required == expected_review else "FAIL"
    print(f"[{status}] {name}")
    print(f"       review_required={result.review_required}")
    for note in result.review_notes:
        print(f"       REVIEW: {note}")
    for note in result.info_notes:
        print(f"       info: {note}")
    print()