from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, UploadFile, File, HTTPException
from sqlalchemy import select

from database import Base, engine, SessionLocal

# Import both models so SQLAlchemy registers both tables.
from models import PurchaseOrder, PurchaseOrderItem

from ocr import extract_text
from llm_extracter import extract_invoice_data
from po_creator import save_purchase_order
from po_matcher import (
    find_purchase_order,
    find_purchase_order_by_details,
    compare_invoice_with_purchase_order,
)


app = FastAPI(
    title="AI Invoice and Purchase Order Auditor",
    version="1.0.0",
)


MAX_FILE_SIZE = 10 * 1024 * 1024

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

SUPPORTED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


@app.on_event("startup")
def create_database_tables():
    """
    Create all SQLAlchemy tables when the server starts.
    """
    print("Creating database tables...")

    Base.metadata.create_all(bind=engine)

    print("Database tables are ready.")


@app.get("/")
def home():
    """
    Check whether the API is running.
    """
    return {
        "message": "AI Invoice and Purchase Order Auditor API is running"
    }


@app.get("/test")
def test_api():
    """
    Simple test endpoint.
    """
    return {
        "status": "working"
    }


@app.post("/upload")
async def upload_invoice(file: UploadFile = File(...)):
    """
    Upload an invoice image, extract its text,
    convert it into structured data using the LLM,
    find or create the related purchase order,
    and compare the invoice with the purchase order.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file was provided."
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Use JPG, JPEG, PNG, or WEBP."
        )

    if file.content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported content type."
        )

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File is too large. Maximum size is 10 MB."
        )

    temporary_file_path = None

    try:
        # Save the uploaded image temporarily.
        with NamedTemporaryFile(
            delete=False,
            suffix=extension
        ) as temporary_file:
            temporary_file.write(file_bytes)
            temporary_file_path = temporary_file.name

        # Step 1: Extract text from the invoice image.
        extracted_text = extract_text(temporary_file_path)

        if not extracted_text or not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from the invoice."
            )

        # Step 2: Convert extracted text into structured invoice data.
        invoice_data = extract_invoice_data(extracted_text)

        # Step 3: Try to find the purchase order using its number.
        purchase_order = None

        if invoice_data.purchase_order_number:
            purchase_order = find_purchase_order(
                invoice_data.purchase_order_number
            )

        # Step 4: If PO number search fails, try the vendor name.
        if purchase_order is None and invoice_data.vendor_name:
            purchase_order = find_purchase_order_by_details(
                vendor_name=invoice_data.vendor_name
            )

        # Step 5: If no PO exists, create one from the invoice data.
        if purchase_order is None and invoice_data.purchase_order_number:
            purchase_order = save_purchase_order(invoice_data)

        # Step 6: Compare invoice data with the purchase order.
        comparison_result = None

        if purchase_order is not None:
            comparison_result = compare_invoice_with_purchase_order(
                invoice_data,
                purchase_order
            )

        return {
            "message": "Invoice processed successfully",
            "invoice": invoice_data,
            "purchase_order": purchase_order,
            "comparison": comparison_result,
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    finally:
        # Delete the temporary image after processing.
        if temporary_file_path:
            temporary_path = Path(temporary_file_path)

            if temporary_path.exists():
                temporary_path.unlink()


@app.post("/add-purchase-order")
async def add_purchase_order(file: UploadFile = File(...)):
    """
    Upload a purchase-order image, extract its text,
    convert it into structured data using the LLM,
    and save it in the database.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file was provided."
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Use JPG, JPEG, PNG, or WEBP."
        )

    if file.content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported content type."
        )

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File is too large. Maximum size is 10 MB."
        )

    temporary_file_path = None

    try:
        # Save the uploaded image temporarily.
        with NamedTemporaryFile(
            delete=False,
            suffix=extension
        ) as temporary_file:
            temporary_file.write(file_bytes)
            temporary_file_path = temporary_file.name

        # Step 1: Extract text from the image.
        extracted_text = extract_text(temporary_file_path)

        if not extracted_text or not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from the image."
            )

        # Step 2: Convert OCR text into structured invoice/PO data.
        invoice_data = extract_invoice_data(extracted_text)

        # Step 3: Save the structured data into the database.
        purchase_order = save_purchase_order(invoice_data)

        return {
            "message": "Purchase order saved successfully",
            "filename": file.filename,
            "extracted_text": extracted_text,
            "extracted_data": invoice_data.model_dump(),
            "purchase_order": purchase_order,
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    finally:
        # Delete the temporary image.
        if temporary_file_path:
            temporary_path = Path(temporary_file_path)

            if temporary_path.exists():
                temporary_path.unlink()

@app.get("/purchase-orders")
def get_purchase_orders():
    """
    Return all purchase orders.
    """
    db = SessionLocal()

    try:
        purchase_orders = db.execute(
            select(PurchaseOrder)
        ).scalars().all()

        return purchase_orders

    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )