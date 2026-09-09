from typing import Optional

from pydantic import BaseModel, Field


class InvoiceItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    tax: Optional[float] = None
    amount: Optional[float] = None


class InvoiceData(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    vendor_name: Optional[str] = None
    purchase_order_number: Optional[str] = None
    items: list[InvoiceItem] = Field(default_factory=list)
    total_amount: Optional[float] = None


class PurchaseOrderItem(BaseModel):
    description: str
    quantity: float
    unit_price: float


class PurchaseOrder(BaseModel):
    po_number: str
    vendor_name: str
    items: list[PurchaseOrderItem]
    total_amount: float


class ItemComparison(BaseModel):
    invoice_description: Optional[str] = None
    po_description: Optional[str] = None
    invoice_quantity: Optional[float] = None
    po_quantity: Optional[float] = None
    invoice_price: Optional[float] = None
    po_price: Optional[float] = None
    quantity_match: bool = False
    price_match: bool = False
    description_match: bool = False


class PurchaseOrderMatch(BaseModel):
    status: str
    reason: str
    purchase_order: Optional[PurchaseOrder] = None
    item_comparisons: list[ItemComparison] = Field(
        default_factory=list
    )
    total_match: Optional[bool] = None