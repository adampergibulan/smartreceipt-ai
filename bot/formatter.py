from typing import List, Optional

from bot.schemas import ReceiptData
from bot.validation import ValidationResult

# Telegram's limit is 4096 characters. Stay a little below it.
TELEGRAM_LIMIT = 4000


def format_quantity(value: Optional[float]) -> str:
    """1.0 -> '1', 0.326 -> '0.326'."""
    if value is None:
        return "not found"
    return f"{value:.3f}".rstrip("0").rstrip(".")


def format_money(value: Optional[float], currency: Optional[str]) -> str:
    """Format an amount. Never assumes a currency that was not read."""
    if value is None:
        return "not found"
    amount = f"{value:,.2f}"
    if currency == "MYR":
        return f"RM{amount}"
    if currency:
        return f"{currency} {amount}"
    return amount


def build_receipt_message(data: ReceiptData, result: ValidationResult) -> str:
    """Create the readable summary shown to the user."""
    # Image could not be used at all
    if not data.is_receipt or data.image_quality == "unreadable":
        lines = [
            "SMARTRECEIPT AI",
            "",
            "❌ I could not read this image as a receipt.",
            "",
        ]
        for note in result.review_notes:
            lines.append(f"• {note}")
        lines.append("")
        lines.append("Please send a clearer photo of the full receipt.")
        return "\n".join(lines)

    currency = data.currency

    # Date, with its source
    if result.receipt_date:
        if result.date_source == "calculated":
            date_text = f"{result.receipt_date} (calculated by app)"
        else:
            date_text = result.receipt_date
    elif data.receipt_date_raw:
        date_text = f"{data.receipt_date_raw} (unclear, please check)"
    else:
        date_text = "not found"

    lines = [
        "SMARTRECEIPT AI",
        "",
        "Receipt Analysis Complete",
        "",
        f"Supplier: {data.supplier_name or 'not found'}",
        f"Date: {date_text}",
        f"Receipt No: {data.receipt_number or 'not found'}",
        "",
        "Items:",
    ]

    if not data.items:
        lines.append("No items could be read.")

    for number, item in enumerate(data.items, start=1):
        quantity = format_quantity(item.quantity)
        if item.quantity is not None and item.unit:
            quantity = f"{quantity} {item.unit}"
        lines.append(f"{number}. {item.item_name}")
        lines.append(f"   Quantity: {quantity}")
        lines.append(f"   Unit Price: {format_money(item.unit_price, currency)}")
        lines.append(f"   Total: {format_money(item.line_total, currency)}")
        lines.append("")

    lines.append(f"Subtotal: {format_money(data.subtotal, currency)}")
    if data.tax_amount is not None:
        lines.append(f"Tax: {format_money(data.tax_amount, currency)}")
    if data.discount_amount is not None:
        lines.append(f"Discount: {format_money(data.discount_amount, currency)}")
    lines.append(f"Grand Total: {format_money(data.grand_total, currency)}")
    lines.append(f"Currency: {currency or 'not clear'}")

    # Values calculated by the app (not read from the receipt)
    if result.items_total is not None:
        lines.append(
            f"Items total (calculated by app): "
            f"{format_money(float(result.items_total), currency)}"
        )

    lines.append("")

    if result.review_required:
        lines.append("⚠️ Please check:")
        for note in result.review_notes:
            lines.append(f"• {note}")
        lines.append("")

    if result.info_notes:
        lines.append("Checked by the app:")
        for note in result.info_notes:
            lines.append(f"• {note}")
        lines.append("")

    if result.review_required:
        lines.append("Status: Needs review. Requires confirmation before saving.")
    else:
        lines.append("Status: Requires confirmation before saving.")

    return "\n".join(lines)


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> List[str]:
    """Split a long message into parts that fit Telegram's limit.
    Splits between lines so no line is cut in half (unless one line is huge)."""
    chunks: List[str] = []
    current = ""

    for line in text.split("\n"):
        # A single line longer than the limit must be cut
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]

        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks