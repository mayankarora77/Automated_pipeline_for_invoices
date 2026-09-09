import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from schemas import InvoiceData


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing from the .env file."
    )

groq = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)


def clean_json_response(raw_response: str) -> str:
    """
    Removes Markdown code fences if the model returns them.
    """
    raw_response = raw_response.strip()

    raw_response = re.sub(
        r"^```json\s*",
        "",
        raw_response,
        flags=re.IGNORECASE,
    )

    raw_response = re.sub(
        r"^```\s*",
        "",
        raw_response,
    )

    raw_response = re.sub(
        r"\s*```$",
        "",
        raw_response,
    )

    return raw_response.strip()


def extract_invoice_data(ocr_text: str) -> InvoiceData:
    if not ocr_text.strip():
        raise ValueError(
            "OCR could not extract any text from the invoice."
        )

    response = groq.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict invoice and purchase-order extraction system. "
                    "Read only the supplied OCR text and return only valid JSON. "
                    "Never invent, assume, or guess values. Use null when a value "
                    "cannot be identified confidently. "

                    "IMPORTANT VENDOR RULES: "
                    "For a purchase order, vendor_name means the supplier or seller "
                    "who will provide the goods. Select the company written in the "
                    "'Supplier Details', 'Supplier', 'Vendor', or 'Seller' section. "
                    "If the OCR contains both a buyer and supplier, always select "
                    "the supplier, not the buyer. "
                    "Never select the company under 'Buyer', 'From', 'Bill To', "
                    "'Ship To', 'Customer', 'Purchaser', or the main company header "
                    "when a separate supplier is present. "

                    "For an invoice, vendor_name means the seller or supplier "
                    "who issued the invoice. Do not select the customer or buyer. "

                    "If the document contains text such as "
                    "'AI_TECH Pvt. Ltd.' near the top and "
                    "'Kunj_Dealers' under 'Supplier Details', the correct "
                    "vendor_name is 'Kunj_Dealers'. "

                    "The purchase order number and invoice number are different. "
                    "Extract purchase_order_number only from a label such as "
                    "'P.O.', 'P.O.#', 'PO Number', 'Purchase Order Number', "
                    "'Order Number', or 'YOUR ORDER NO.'. "
                    "Never use an invoice number as the purchase order number. "

                    "For item descriptions, keep only the product or service name. "
                    "Remove serial number, HSN code, quantity, unit price, tax, "
                    "and total amount from the description."
                ),
            },
            {
                "role": "user",
                "content": f"""
Extract structured data from the OCR text below.

Before producing JSON, follow this internal process:

1. Find every company name in the OCR text.
2. Identify which company is the buyer and which company is the supplier.
3. For a purchase order, choose the company under Supplier Details,
   Supplier, Vendor, or Seller.
4. Do not choose the buyer/company shown in the document header.
5. If there is no clearly identifiable supplier, return null for vendor_name.
6. Extract the PO number only from an explicit PO-related label.
7. Extract item descriptions without table-column values.

Return exactly this JSON structure:

{{
    "invoice_number": null,
    "invoice_date": null,
    "due_date": null,
    "vendor_name": null,
    "purchase_order_number": null,
    "items": [],
    "total_amount": null
}}

Each item must have this structure:

{{
    "description": null,
    "quantity": null,
    "price": null,
    "tax": null,
    "amount": null
}}

Rules:

- Keep invoice_number and purchase_order_number as strings.
- Keep dates as strings.
- Convert quantity, price, tax, amount, and total_amount to numbers.
- Use null for missing values.
- Do not invent values.
- Do not add explanations outside the JSON.

Vendor extraction:
- On a purchase order, vendor_name must be the supplier/seller.
- Prefer the name directly under or beside:
  Supplier Details, Supplier, Vendor, or Seller.
- Do not use the buyer's company name.
- Do not use the company under:
  Buyer, From, Bill To, Ship To, Customer, or Purchaser.
- If both buyer and supplier are present, the supplier must be selected.
- On an invoice, vendor_name must be the seller who issued the invoice.

Purchase order extraction:
- Extract purchase_order_number only from:
  P.O.#, P.O., PO Number, Purchase Order Number,
  Order Number, or YOUR ORDER NO.
- Never confuse invoice_number with purchase_order_number.
- Return null if no PO number is explicitly available.

Item extraction:
- description must contain only the product or service name.
- Do not include S.No., HSN code, quantity, price, tax, or total.
- quantity must be numeric.
- price means unit price.
- amount means the line-item total.

OCR text:
{ocr_text}
""",
            },
        ],
        response_format={"type": "json_object"},
    )

    raw_response = response.choices[0].message.content

    if not raw_response:
        raise ValueError(
            "Groq returned an empty response."
        )

    cleaned_response = clean_json_response(raw_response)

    try:
        parsed_json = json.loads(cleaned_response)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Groq returned invalid JSON: {error}"
        ) from error

    return InvoiceData.model_validate(parsed_json)