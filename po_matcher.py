from difflib import SequenceMatcher
from decimal import Decimal

from sqlalchemy import select

from database import SessionLocal
from models import PurchaseOrder
import re

from difflib import SequenceMatcher
from decimal import Decimal


AMOUNT_TOLERANCE = Decimal("0.01")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    value = value.lower().strip()

    # Remove every character except letters and numbers.
    return "".join(
        character
        for character in value
        if character.isalnum()
    )


def descriptions_match(
    invoice_description: str | None,
    po_description: str | None,
) -> bool:
    invoice_text = normalize_text(invoice_description)
    po_text = normalize_text(po_description)

    if not invoice_text or not po_text:
        return False

    # Exact normalized match.
    if invoice_text == po_text:
        return True

    # Compare important words instead of the complete sentence.
    invoice_words = set(
        re.findall(r"[a-z0-9]+", invoice_description.lower())
    )

    po_words = set(
        re.findall(r"[a-z0-9]+", po_description.lower())
    )

    # Remove generic words that do not identify the product.
    ignored_words = {
        "laptop",
        "computer",
        "the",
        "a",
        "an",
        "and",
        "with",
        "windows",
        "home",
        "pro",
    }

    invoice_words -= ignored_words
    po_words -= ignored_words

    if not invoice_words or not po_words:
        return False

    common_words = invoice_words.intersection(po_words)

    # At least 60% of the important words should match.
    word_similarity = len(common_words) / min(
        len(invoice_words),
        len(po_words),
    )

    if word_similarity >= 0.60:
        return True

    # Keep the original fuzzy comparison as a fallback.
    similarity = SequenceMatcher(
        None,
        invoice_text,
        po_text,
    ).ratio()

    return similarity >= 0.80


def find_purchase_order(po_number: str | None):
    """
    Find a PO by its exact PO number.
    """

    if not po_number:
        return None

    db = SessionLocal()

    try:
        purchase_order = db.scalars(
            select(PurchaseOrder).where(
                PurchaseOrder.po_number == po_number.strip()
            )
        ).first()

        if not purchase_order:
            return None

        return convert_purchase_order_to_dict(
            purchase_order
        )

    finally:
        db.close()


def find_purchase_order_by_details(
    vendor_name: str | None = None,
    total_amount: float | None = None,
):
    """
    Fallback search using vendor name and total amount.
    """

    if not vendor_name and total_amount is None:
        return None

    db = SessionLocal()

    try:
        statement = select(PurchaseOrder)

        if vendor_name:
            statement = statement.where(
                PurchaseOrder.vendor_name.ilike(
                    f"%{vendor_name.strip()}%"
                )
            )

        purchase_orders = db.scalars(statement).all()

        if not purchase_orders:
            return None

        if total_amount is not None:
            invoice_total = Decimal(
                str(total_amount)
            )

            for purchase_order in purchase_orders:
                po_total = Decimal(
                    str(purchase_order.total_amount or 0)
                )

                if abs(invoice_total - po_total) <= AMOUNT_TOLERANCE:
                    return convert_purchase_order_to_dict(
                        purchase_order
                    )

        return convert_purchase_order_to_dict(
            purchase_orders[0]
        )

    finally:
        db.close()


def convert_purchase_order_to_dict(
    purchase_order,
) -> dict:
    return {
        "id": purchase_order.id,
        "po_number": purchase_order.po_number,
        "vendor_name": purchase_order.vendor_name,
        "total_amount": float(
            purchase_order.total_amount or 0
        ),
        "status": purchase_order.status,
        "items": [
            {
                "description": item.description,
                "quantity": float(item.quantity or 0),
                "unit_price": float(item.unit_price or 0),
            }
            for item in purchase_order.items
        ],
    }


def compare_invoice_with_purchase_order(
    invoice_data,
    purchase_order,
):
    """
    Compare invoice data with a purchase order.
    """

    if purchase_order is None:
        return {
            "status": "not_matched",
            "message": "No matching purchase order was found.",
            "differences": [],
        }

    differences = []

    invoice_vendor = normalize_text(
        invoice_data.vendor_name
    )

    po_vendor = normalize_text(
        purchase_order["vendor_name"]
    )

    if invoice_vendor and po_vendor:
        if invoice_vendor != po_vendor:
            differences.append({
                "field": "vendor_name",
                "invoice_value": invoice_data.vendor_name,
                "purchase_order_value": purchase_order[
                    "vendor_name"
                ],
                "message": "Vendor names do not match.",
            })

    invoice_total = invoice_data.total_amount
    po_total = purchase_order["total_amount"]

    total_match = True

    if invoice_total is not None:
        total_match = (
            abs(
                Decimal(str(invoice_total))
                - Decimal(str(po_total))
            )
            <= AMOUNT_TOLERANCE
        )

        if not total_match:
            differences.append({
                "field": "total_amount",
                "invoice_value": float(invoice_total),
                "purchase_order_value": float(po_total),
                "message": (
                    "Invoice total does not match "
                    "purchase-order total."
                ),
            })

    invoice_items = invoice_data.items or []
    po_items = purchase_order["items"]

    if len(invoice_items) != len(po_items):
        differences.append({
            "field": "item_count",
            "invoice_value": len(invoice_items),
            "purchase_order_value": len(po_items),
            "message": (
                "The number of invoice items does not match "
                "the number of purchase-order items."
            ),
        })

    comparison_count = min(
        len(invoice_items),
        len(po_items),
    )

    for index in range(comparison_count):
        invoice_item = invoice_items[index]
        po_item = po_items[index]

        description_match = descriptions_match(
            invoice_item.description,
            po_item["description"],
        )

        if not description_match:
            differences.append({
                "field": f"items[{index}].description",
                "invoice_value": invoice_item.description,
                "purchase_order_value": po_item[
                    "description"
                ],
                "message": "Item descriptions do not match.",
            })

        quantity_match = True

        if invoice_item.quantity is not None:
            quantity_match = (
                abs(
                    Decimal(str(invoice_item.quantity))
                    - Decimal(str(po_item["quantity"]))
                )
                <= AMOUNT_TOLERANCE
            )

            if not quantity_match:
                differences.append({
                    "field": f"items[{index}].quantity",
                    "invoice_value": float(
                        invoice_item.quantity
                    ),
                    "purchase_order_value": po_item[
                        "quantity"
                    ],
                    "message": "Item quantities do not match.",
                })

        price_match = True

        if invoice_item.price is not None:
            price_match = (
                abs(
                    Decimal(str(invoice_item.price))
                    - Decimal(str(po_item["unit_price"]))
                )
                <= AMOUNT_TOLERANCE
            )

            if not price_match:
                differences.append({
                    "field": f"items[{index}].price",
                    "invoice_value": float(
                        invoice_item.price
                    ),
                    "purchase_order_value": po_item[
                        "unit_price"
                    ],
                    "message": "Item prices do not match.",
                })

    status = (
        "matched"
        if not differences
        else "mismatched"
    )

    return {
        "status": status,
        "message": (
            "Invoice matches the purchase order."
            if status == "matched"
            else "Invoice contains differences "
                 "from the purchase order."
        ),
        "differences": differences,
        "total_match": total_match,
    }