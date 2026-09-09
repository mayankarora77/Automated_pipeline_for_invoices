import json
import mimetypes
import os

import requests
import gradio as gr


API_URL = "http://127.0.0.1:8000"


def format_json(data):
    if data is None:
        return "No data available."

    return json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
    )


def prepare_file(file_path):
    """
    Prepare the uploaded file with the correct MIME type.
    """
    filename = os.path.basename(file_path)

    content_type = (
        mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )

    return filename, content_type


def upload_invoice_or_po(file):
    if file is None:
        return (
            "Please upload a document.",
            "",
            "",
            "",
        )

    try:
        filename, content_type = prepare_file(file)

        with open(file, "rb") as uploaded_file:
            response = requests.post(
                f"{API_URL}/upload",
                files={
                    "file": (
                        filename,
                        uploaded_file,
                        content_type,
                    )
                },
                timeout=120,
            )

        if response.status_code != 200:
            return (
                f"API Error: {response.status_code}",
                response.text,
                "",
                "",
            )

        result = response.json()

        invoice_data = result.get("invoice", {})
        purchase_order = result.get("purchase_order", {})
        comparison = result.get("comparison", {})

        status = comparison.get("status", "unknown")

        if status == "matched":
            status_message = (
                "MATCHED\n\n"
                "The invoice matches the purchase order."
            )

        elif status == "mismatched":
            status_message = (
                "MISMATCHED\n\n"
                "The invoice contains differences "
                "from the purchase order."
            )

        else:
            status_message = status

        differences = comparison.get("differences", [])

        if differences:
            difference_text = "\n\n".join(
                [
                    (
                        f"Field: {difference.get('field')}\n"
                        f"Invoice value: "
                        f"{difference.get('invoice_value')}\n"
                        f"PO value: "
                        f"{difference.get('purchase_order_value')}\n"
                        f"Message: {difference.get('message')}"
                    )
                    for difference in differences
                ]
            )
        else:
            difference_text = "No differences found."

        return (
            status_message,
            format_json(invoice_data),
            format_json(purchase_order),
            difference_text,
        )

    except requests.exceptions.ConnectionError:
        return (
            "Connection failed.",
            "Please start your FastAPI server first.",
            "",
            "",
        )

    except requests.exceptions.Timeout:
        return (
            "Request timed out.",
            "The backend took too long to respond.",
            "",
            "",
        )

    except Exception as error:
        return (
            "Unexpected error.",
            str(error),
            "",
            "",
        )


def create_purchase_order(file):
    if file is None:
        return "Please upload a purchase-order document."

    try:
        filename, content_type = prepare_file(file)

        with open(file, "rb") as uploaded_file:
            response = requests.post(
                f"{API_URL}/add-purchase-order",
                files={
                    "file": (
                        filename,
                        uploaded_file,
                        content_type,
                    )
                },
                timeout=120,
            )

        if response.status_code != 200:
            return (
                f"API Error: {response.status_code}\n\n"
                f"{response.text}"
            )

        return format_json(response.json())

    except requests.exceptions.ConnectionError:
        return (
            "Connection failed.\n\n"
            "Please start your FastAPI server first."
        )

    except requests.exceptions.Timeout:
        return (
            "Request timed out.\n\n"
            "The backend took too long to respond."
        )

    except Exception as error:
        return str(error)


def get_purchase_orders():
    try:
        response = requests.get(
            f"{API_URL}/purchase-orders",
            timeout=30,
        )

        if response.status_code != 200:
            return (
                f"API Error: {response.status_code}\n\n"
                f"{response.text}"
            )

        return format_json(response.json())

    except requests.exceptions.ConnectionError:
        return (
            "Connection failed. "
            "Please start your FastAPI server first."
        )

    except requests.exceptions.Timeout:
        return "Request timed out."

    except Exception as error:
        return str(error)


custom_css = """
body {
    background: #f4f7fb;
}

.gradio-container {
    max-width: 1250px !important;
    margin: auto !important;
}

.app-header {
    background: linear-gradient(135deg, #172554, #2563eb);
    color: white;
    padding: 28px;
    border-radius: 18px;
    margin-bottom: 20px;
}

.app-header h1 {
    margin: 0;
    font-size: 32px;
}

.app-header p {
    margin: 8px 0 0;
    opacity: 0.9;
    font-size: 16px;
}

.status-box textarea {
    font-size: 18px !important;
    font-weight: 700 !important;
}

footer {
    display: none !important;
}
"""


with gr.Blocks(
    title="AI Invoice Auditor",
    theme=gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="slate",
    ),
    css=custom_css,
) as demo:

    gr.HTML(
        """
        <div class="app-header">
            <h1>AI Invoice & Purchase Order Auditor</h1>
            <p>
                Upload documents, extract important details, and verify
                invoices against purchase orders automatically.
            </p>
        </div>
        """
    )

    with gr.Tabs():

        with gr.Tab("Audit Invoice"):
            gr.Markdown(
                """
                ### Upload an invoice

                The system will extract the invoice details and compare
                them with the matching purchase order.
                """
            )

            with gr.Row():

                with gr.Column(scale=1):
                    invoice_file = gr.File(
                        label="Upload Invoice",
                        file_types=[
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".pdf",
                        ],
                        type="filepath",
                    )

                    audit_button = gr.Button(
                        "Audit Invoice",
                        variant="primary",
                        size="lg",
                    )

                with gr.Column(scale=1):
                    audit_status = gr.Textbox(
                        label="Audit Result",
                        lines=4,
                        elem_classes=["status-box"],
                    )

            with gr.Row():

                invoice_output = gr.Code(
                    label="Extracted Invoice Data",
                    language="json",
                )

                po_output = gr.Code(
                    label="Matched Purchase Order",
                    language="json",
                )

            differences_output = gr.Textbox(
                label="Differences Found",
                lines=10,
            )

            audit_button.click(
                fn=upload_invoice_or_po,
                inputs=invoice_file,
                outputs=[
                    audit_status,
                    invoice_output,
                    po_output,
                    differences_output,
                ],
            )

        with gr.Tab("Create Purchase Order"):
            gr.Markdown(
                """
                ### Create a purchase order

                Upload a purchase-order document. Its details will be
                extracted and saved to the database.
                """
            )

            with gr.Row():

                with gr.Column(scale=1):
                    po_file = gr.File(
                        label="Upload Purchase Order",
                        file_types=[
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".pdf",
                        ],
                        type="filepath",
                    )

                    create_po_button = gr.Button(
                        "Create Purchase Order",
                        variant="primary",
                        size="lg",
                    )

                with gr.Column(scale=1):
                    po_creation_output = gr.Code(
                        label="Purchase Order Creation Result",
                        language="json",
                    )

            create_po_button.click(
                fn=create_purchase_order,
                inputs=po_file,
                outputs=po_creation_output,
            )

        with gr.Tab("Saved Purchase Orders"):
            gr.Markdown(
                """
                ### Saved purchase orders

                View all purchase orders currently stored in the database.
                """
            )

            refresh_button = gr.Button(
                "Refresh Purchase Orders",
                variant="secondary",
            )

            saved_pos_output = gr.Code(
                label="Saved Purchase Orders",
                language="json",
            )

            refresh_button.click(
                fn=get_purchase_orders,
                inputs=None,
                outputs=saved_pos_output,
            )

    gr.Markdown(
        """
        ---
        **Backend:** FastAPI  
        **Interface:** Gradio  
        **Processing:** OCR + LLM extraction + database comparison
        """
    )


if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
    )