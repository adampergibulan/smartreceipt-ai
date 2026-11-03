from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ReceiptItem(BaseModel):
    item_name: str = Field(
        description="Item name exactly as printed on the receipt. "
        "Do not translate, rename, or correct it."
    )
    quantity: Optional[float] = Field(
        description="Quantity as a number, or null if not printed or unreadable."
    )
    unit: Optional[str] = Field(
        description="Unit as printed (for example KG, PCS, BTL), or null."
    )
    unit_price: Optional[float] = Field(
        description="Price per unit as a number without currency symbol, "
        "or null if not printed."
    )
    line_total: Optional[float] = Field(
        description="Total for this line as a number without currency symbol, "
        "or null if not printed."
    )


class ReceiptData(BaseModel):
    is_receipt: bool = Field(
        description="True only if the image is a receipt or invoice."
    )
    image_quality: Literal["clear", "partly_readable", "unreadable"] = Field(
        description="How readable the image is."
    )
    supplier_name: Optional[str] = Field(
        description="Shop or supplier name as printed, or null if not visible."
    )
    receipt_date: Optional[str] = Field(
        description="Date as YYYY-MM-DD, only if the day and month are "
        "unambiguous. Otherwise null."
    )
    receipt_date_raw: Optional[str] = Field(
        description="The date exactly as printed, or null if no date is visible."
    )
    receipt_number: Optional[str] = Field(
        description="Receipt or invoice number as printed, or null."
    )
    items: List[ReceiptItem] = Field(
        description="All purchased items. Empty list if none are readable."
    )
    subtotal: Optional[float] = Field(
        description="Subtotal printed on the receipt, or null."
    )
    tax_amount: Optional[float] = Field(
        description="Tax amount printed on the receipt (SST, GST, etc.), or null."
    )
    discount_amount: Optional[float] = Field(
        description="Discount amount printed on the receipt, or null."
    )
    grand_total: Optional[float] = Field(
        description="Final total printed on the receipt, or null."
    )
    currency: Optional[str] = Field(
        description="Currency code. Use MYR only if RM or MYR is clearly "
        "printed. Otherwise null."
    )
    ai_notes: List[str] = Field(
        description="Short notes about anything unclear, cut off, or ambiguous."
    )