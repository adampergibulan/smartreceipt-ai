from bot.formatter import build_receipt_message, split_message
from bot.schemas import ReceiptData
from bot.validation import validate_receipt


def make(**overrides):
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


def show(title, data):
    print("=" * 50)
    print(title)
    print("=" * 50)
    print(build_receipt_message(data, validate_receipt(data)))
    print()


# 1. Good receipt
show("TEST A: good receipt (MYR)", make())

# 2. Missing values and unclear currency and date
show("TEST B: missing values", make(
    supplier_name=None, receipt_number=None, currency=None,
    receipt_date=None, receipt_date_raw="03/04/26",
    items=[{"item_name": "AJI-SHIO_BLACK*PEPPER", "quantity": None,
            "unit": None, "unit_price": None, "line_total": 5.3}],
    subtotal=None, grand_total=5.3))

# 3. Blurry image
show("TEST C: blurry image", make(
    image_quality="unreadable", supplier_name=None, receipt_date=None,
    receipt_date_raw=None, receipt_number=None, items=[],
    subtotal=None, grand_total=None, currency=None))

# 4. Very long receipt, to test message splitting
many_items = [
    {"item_name": f"Test item number {i}", "quantity": 1, "unit": "PCS",
     "unit_price": 1.0, "line_total": 1.0}
    for i in range(1, 121)
]
long_data = make(items=many_items, subtotal=120.0, grand_total=120.0)
long_text = build_receipt_message(long_data, validate_receipt(long_data))
parts = split_message(long_text)
print("=" * 50)
print("TEST D: long receipt (120 items)")
print("=" * 50)
print(f"Total length: {len(long_text)} characters")
print(f"Split into {len(parts)} messages")
print(f"Longest part: {max(len(p) for p in parts)} characters (limit 4096)")