from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
import pytesseract


TESSERACT_PATH = Path(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)


def extract_text(image_path: str) -> str:
    image = Image.open(image_path)

    try:
        image = image.convert("RGB")

        # Improve OCR quality for invoice images.
        image = image.resize(
            (
                image.width * 2,
                image.height * 2,
            )
        )

        image = ImageEnhance.Contrast(image).enhance(1.5)
        image = image.filter(ImageFilter.SHARPEN)

        extracted_text = pytesseract.image_to_string(
            image,
            config="--psm 6",
        )

        return extracted_text.strip()

    finally:
        image.close()


if __name__ == "__main__":
    invoice_path = "invoice.jpeg"

    if not Path(invoice_path).exists():
        print(f"File not found: {invoice_path}")
    else:
        text = extract_text(invoice_path)

        print("\n----- EXTRACTED INVOICE TEXT -----\n")
        print(text)