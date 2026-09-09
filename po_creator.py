from sqlalchemy import select

from database import SessionLocal
from models import PurchaseOrder, PurchaseOrderItem


def save_purchase_order(invoice_data):
    """
    Create a purchase order from extracted invoice data.

    If the PO already exists, return the existing PO instead
    of creating a duplicate.
    """

    po_number = invoice_data.purchase_order_number

    if not po_number:
        raise ValueError(
            "Purchase order number was not found in the invoice. "
            "The invoice must contain a PO number before a PO "
            "can be created automatically."
        )

    po_number = po_number.strip()

    db = SessionLocal()

    try:
        existing_po = db.scalars(
            select(PurchaseOrder).where(
                PurchaseOrder.po_number == po_number
            )
        ).first()

        if existing_po:
            return {
                "message": "Purchase order already exists.",
                "created": False,
                "purchase_order_id": existing_po.id,
                "po_number": existing_po.po_number,
                "vendor_name": existing_po.vendor_name,
                "total_amount": float(
                    existing_po.total_amount or 0
                ),
                "items_saved": len(existing_po.items),
            }

        purchase_order = PurchaseOrder(
            po_number=po_number,
            vendor_name=(
                invoice_data.vendor_name or "Unknown Vendor"
            ).strip(),
            total_amount=invoice_data.total_amount or 0,
            status="system_created",
        )

        db.add(purchase_order)
        db.flush()

        saved_items = 0

        for invoice_item in invoice_data.items:
            description = (
                invoice_item.description or "Unknown Item"
            ).strip()

            quantity = invoice_item.quantity or 0
            unit_price = invoice_item.price or 0

            purchase_order_item = PurchaseOrderItem(
                purchase_order_id=purchase_order.id,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
            )

            db.add(purchase_order_item)
            saved_items += 1

        db.commit()
        db.refresh(purchase_order)

        return {
            "message": "Purchase order created automatically.",
            "created": True,
            "purchase_order_id": purchase_order.id,
            "po_number": purchase_order.po_number,
            "vendor_name": purchase_order.vendor_name,
            "total_amount": float(
                purchase_order.total_amount or 0
            ),
            "items_saved": saved_items,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()