import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import product
from typing import List, Optional

from bot.schemas import ReceiptData

# Allowed small differences. Change these if your receipts need it.
LINE_TOLERANCE = Decimal("0.02")      # quantity x unit price vs line total
SUM_TOLERANCE = Decimal("0.02")       # sum of lines vs subtotal
ROUNDING_TOLERANCE = Decimal("0.03")  # grand total (cash rounding to 5 sen)

DATE_PATTERN = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4}|\d{2})")


@dataclass
class ValidationResult:
    receipt_date: Optional[str]      # final date as YYYY-MM-DD, or None
    date_source: str                 # "read", "calculated", or "missing"
    items_total: Optional[Decimal]   # calculated by the app
    review_required: bool
    review_notes: List[str]          # problems a person must check
    info_notes: List[str]            # checks that passed or were calculated


def money(value) -> Optional[Decimal]:
    """Turn a float into an exact Decimal (avoids 0.1 + 0.2 problems)."""
    if value is None:
        return None
    return Decimal(str(value))


def parse_raw_date(raw: Optional[str]):
    """Try to understand a printed date like 19/10/26.
    Returns (iso_date, problem). iso_date is None if the date is unclear."""
    if not raw:
        return None, None

    match = DATE_PATTERN.search(raw)
    if not match:
        return None, f"Date '{raw}' is in a format the app does not recognise."

    first, second, year = (int(g) for g in match.groups())
    if year < 100:
        year += 2000

    # Day-first is only certain when one number is bigger than 12
    if first > 12 and second <= 12:
        day, month = first, second
    elif second > 12 and first <= 12:
        day, month = second, first
    elif first == second:
        day, month = first, second
    else:
        return None, f"Date '{raw}' is ambiguous (day and month could be swapped)."

    try:
        return date(year, month, day).isoformat(), None
    except ValueError:
        return None, f"Date '{raw}' is not a valid calendar date."


def validate_receipt(data: ReceiptData) -> ValidationResult:
    notes: List[str] = []   # need manual review
    info: List[str] = []    # passed checks or app calculations

    # --- Is this usable at all? ---
    if not data.is_receipt:
        notes.append("The image does not look like a receipt or invoice.")
        return ValidationResult(None, "missing", None, True, notes, info)

    if data.image_quality == "unreadable":
        notes.append("The image is too blurry to read. Please send a clearer photo.")
        return ValidationResult(None, "missing", None, True, notes, info)

    if data.image_quality == "partly_readable":
        notes.append("The image is only partly readable. Please check every value.")

    # --- Header fields ---
    if not (data.supplier_name or "").strip():
        notes.append("Supplier name is missing.")
    if not (data.receipt_number or "").strip():
        notes.append("Receipt number is missing.")

    # --- Date ---
    final_date = None
    date_source = "missing"
    if data.receipt_date:
        try:
            final_date = date.fromisoformat(data.receipt_date).isoformat()
            date_source = "read"
        except ValueError:
            notes.append(f"Date '{data.receipt_date}' is not valid.")
    if final_date is None and data.receipt_date_raw:
        final_date, problem = parse_raw_date(data.receipt_date_raw)
        if final_date:
            date_source = "calculated"
            info.append(
                f"Date {final_date} was worked out by the app from "
                f"'{data.receipt_date_raw}' (day first)."
            )
        elif problem:
            notes.append(problem)
    if final_date is None and not data.receipt_date_raw:
        notes.append("Date is missing or not visible.")
    if final_date and date.fromisoformat(final_date) > date.today():
        notes.append(f"Date {final_date} is in the future. Please check it.")

    # --- Currency (never assumed) ---
    if not data.currency:
        notes.append("Currency is not clear on the receipt (not assumed).")

    # --- Items ---
    if not data.items:
        notes.append("No items could be read.")

    all_line_totals = bool(data.items)
    running_total = Decimal("0")

    for number, item in enumerate(data.items, start=1):
        name = (item.item_name or "").strip()
        label = f"Item {number} ({name})" if name else f"Item {number}"
        if not name:
            notes.append(f"Item {number} has no name.")

        quantity = money(item.quantity)
        unit_price = money(item.unit_price)
        line_total = money(item.line_total)

        missing = []
        if quantity is None:
            missing.append("quantity")
        if unit_price is None:
            missing.append("unit price")
        if line_total is None:
            missing.append("line total")
        if missing:
            notes.append(f"{label}: missing {', '.join(missing)}.")

        if quantity is not None and quantity <= 0:
            notes.append(f"{label}: quantity is zero or negative.")
        if unit_price is not None and unit_price < 0:
            notes.append(f"{label}: unit price is negative.")
        if line_total is not None and line_total < 0:
            notes.append(f"{label}: line total is negative.")

        if line_total is None:
            all_line_totals = False
        else:
            running_total += line_total

        if quantity is not None and unit_price is not None and line_total is not None:
            expected = quantity * unit_price
            if abs(expected - line_total) > LINE_TOLERANCE:
                notes.append(
                    f"{label}: quantity x unit price = {expected:.2f} "
                    f"but line total is {line_total:.2f}."
                )

    items_total = running_total if all_line_totals else None

    # --- Compare items with subtotal ---
    subtotal = money(data.subtotal)
    if items_total is not None and subtotal is not None:
        if abs(items_total - subtotal) > SUM_TOLERANCE:
            notes.append(
                f"Line totals add up to {items_total:.2f} "
                f"but the subtotal is {subtotal:.2f}."
            )
        else:
            info.append(
                f"Line totals add up to the subtotal ({items_total:.2f}), "
                "checked by the app."
            )

    # --- Compare with grand total ---
    grand = money(data.grand_total)
    tax = money(data.tax_amount)
    discount = money(data.discount_amount)

    if grand is None:
        notes.append("Grand total is missing.")
    elif grand <= 0:
        notes.append("Grand total is zero or negative.")
    else:
        if subtotal is not None:
            base, base_name = subtotal, "subtotal"
        elif items_total is not None:
            base, base_name = items_total, "sum of line totals"
        else:
            base, base_name = None, ""

        if base is None:
            notes.append(
                "Grand total could not be checked (no subtotal or complete line totals)."
            )
        else:
            # Try every formula that uses only values that were actually read
            tax_choices = [False, True] if tax is not None else [False]
            discount_choices = [False, True] if discount is not None else [False]

            best = None  # (difference, expected, formula text)
            for use_tax, use_discount in product(tax_choices, discount_choices):
                expected = base
                formula = base_name
                if use_discount:
                    expected -= discount
                    formula += " - discount"
                if use_tax:
                    expected += tax
                    formula += " + tax"
                difference = abs(expected - grand)
                if best is None or difference < best[0]:
                    best = (difference, expected, formula)

            difference, expected, formula = best
            if difference == 0:
                info.append(f"Grand total matches the {formula}, checked by the app.")
            elif difference <= ROUNDING_TOLERANCE:
                info.append(
                    f"Grand total differs from the {formula} by {difference:.2f}, "
                    "treated as rounding."
                )
            else:
                message = (
                    f"Grand total is {grand:.2f} but the {formula} is "
                    f"{expected:.2f} (difference {difference:.2f})."
                )
                if tax is None or discount is None:
                    message += " Tax or discount was not read and may explain this."
                notes.append(message)

    return ValidationResult(
        receipt_date=final_date,
        date_source=date_source,
        items_total=items_total,
        review_required=bool(notes),
        review_notes=notes,
        info_notes=info,
    )