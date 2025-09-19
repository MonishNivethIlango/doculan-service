import json
import os
import fitz  # PyMuPDF
import base64
from io import BytesIO
from PIL import Image
import logging

from repositories.s3_repo import s3_upload_bytes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO
from pathlib import Path
def get_font_path_by_name(font_name: str) -> str:
    # Map font names to actual .ttf files
    font_map = {
        "dancingscript": "fonts/DancingScript-Regular.ttf",
        "pacifico": "fonts/Pacifico-Regular.ttf",
        "dejavusans": "fonts/DejaVuSans.ttf",
        "greatvibes": "fonts/GreatVibes-Regular.ttf",
        "cursive": "fonts/DancingScript-Regular.ttf",
        "helvetica": "fonts/Helvetica.ttf",  # if available
        "sacramento": "fonts/Sacramento-Regular.ttf",  # if available
        "yellowtail": "fonts/Yellowtail-Regular.ttf",  # if available
        "marckscript":"fonts/MarckScript-Regular.ttf"
        # Add more mappings as needed
    }
    return font_map.get(font_name.lower())
def generate_signature_b64_from_fontname(
    text: str,
    font_name: str,
    font_size: int = 28,  # Optimal for the box
    image_size = (250, 60),
    text_color=(0, 0, 0),
    bg_color=(255, 255, 255, 0)
) -> str:
    font_path = get_font_path_by_name(font_name)
    if not font_path or not Path(font_path).exists():
        raise ValueError(f"Font '{font_name}' is not available or path invalid.")

    font = ImageFont.truetype(font_path, font_size)
    image = Image.new("RGBA", image_size, bg_color)
    draw = ImageDraw.Draw(image)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (image_size[0] - text_width) / 2
    y = (image_size[1] - text_height) / 2

    draw.text((x, y), text, font=font, fill=text_color)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"



class PDFFieldInserter:
    def __init__(self, fonts_dir="fonts"):
        self.fonts_dir = fonts_dir
        self.font_name_to_file = {}
        self._registered_fonts = {}
        self.load_fonts_from_directory()

    def load_fonts_from_directory(self):
        if not os.path.isdir(self.fonts_dir):
            logger.warning(f"Fonts directory '{self.fonts_dir}' does not exist.")
            return

        for filename in os.listdir(self.fonts_dir):
            if filename.lower().endswith((".ttf", ".otf")):
                friendly_name = os.path.splitext(filename)[0].replace("-Regular", "").title()
                self.font_name_to_file[friendly_name] = os.path.join(self.fonts_dir, filename)
        logger.info(f"Loaded fonts: {list(self.font_name_to_file.keys())}")

    def get_valid_font(self, pdf_doc, font_friendly_name: str) -> str:
        font_path = self.font_name_to_file.get(font_friendly_name)
        if not font_path or not os.path.isfile(font_path):
            logger.warning(f"Font '{font_friendly_name}' not found. Falling back to 'helv'.")
            return "helv"

        cache_key = (id(pdf_doc), font_friendly_name)
        if cache_key in self._registered_fonts:
            return self._registered_fonts[cache_key]

        try:
            pdf_doc.insert_font(font_friendly_name, fontfile=font_path)
            self._registered_fonts[cache_key] = font_friendly_name
            logger.info(f"Registered font '{font_friendly_name}' for document id {id(pdf_doc)}")
            return font_friendly_name
        except Exception as e:
            logger.error(f"Font registration error for '{font_friendly_name}': {e}")
            return "helv"

    def transform_field_coordinates(self, email, field, page_number, pdf_doc, ui_pdf_height, ui_pdf_width):
        page = pdf_doc[page_number]
        actual_width, actual_height = page.rect.width, page.rect.height
        scale_x = actual_width / ui_pdf_width
        scale_y = actual_height / ui_pdf_height
        x = field.get("x", 0) * scale_x
        y = field.get("y", 0) * scale_y
        width = field.get("width", 200) * scale_x
        height = field.get("height", 150) * scale_y
        value = field.get("value", "")
        field_type = field.get("type")
        style = field.get("style", "drawn")
        return field_type, height, page, style, value, width, x, y

    def insert_tracking_id(self, pdf_doc, tracking_id):
        for page in pdf_doc:
            font_name = self.get_valid_font(pdf_doc, "helv")
            font_size = 8
            margin = 10
            text = f"Tracking_ID: {tracking_id}"
            text_width = fitz.get_text_length(text, fontname=font_name, fontsize=font_size)
            x = page.rect.width - text_width - margin
            y = page.rect.height - margin
            page.insert_text((x, y), text, fontsize=font_size, fontname=font_name, color=(0, 0, 0))

    def insert_wrapped_textarea_field(self, field, page, pdf_doc, value, x, y, width, height):
        try:
            font_name_req = field.get("font", "helv")
            font_name = self.get_valid_font(pdf_doc, font_name_req)
            font_size = field.get("font_size", 10)

            # Break text into lines based on width
            words = str(value).split()
            lines = []
            line = ""
            for word in words:
                test_line = f"{line} {word}".strip()
                text_width = fitz.get_text_length(test_line, fontsize=font_size, fontname=font_name)
                if text_width <= width:
                    line = test_line
                else:
                    lines.append(line)
                    line = word
            if line:
                lines.append(line)

            # Insert each line with spacing, clip if exceeds height
            line_height = font_size + 2
            max_lines = int(height // line_height)
            for i, line in enumerate(lines[:max_lines]):
                page.insert_text((x, y + i * line_height), line, fontsize=font_size, fontname=font_name,
                                 color=(0, 0, 0))

        except Exception as e:
            logger.error(f"Failed to insert wrapped textarea: {e}")

    def insert_field_value_to_pdf(self,email, field, field_type, height, page, page_number, pdf_doc, style, value, width, x, y, tracking_id, party_id):
        if field_type in {"text", "email", "number"}:
            self.insert_text_field(field, page, pdf_doc, value, x, y)

        elif field_type == "textarea":
            self.insert_wrapped_textarea_field(field, page, pdf_doc, value, x, y, width, height)

        elif field_type == "signature":
            if style == "drawn" and isinstance(value, str) and value.startswith("data:image"):
                data = value.split(",")[1]
                metadata_key = f"{email}/signatures/{tracking_id}/signatures/{party_id}.json"
                logger.info(f"drawn : {value}")
                metadata_dict = {
                    str(party_id): {
                        "style": style,
                        "s3_key": value
                    }
                }
                json_data = json.dumps(metadata_dict).encode("utf-8")

                s3_upload_bytes(json_data, metadata_key, content_type="application/json")

                image_data = base64.b64decode(data)
                image = Image.open(BytesIO(image_data))
                if image.mode == "RGBA":
                    self.insert_transparent_signature(height, image, page, width, x, y)
                else:
                    self.insert_flat_signature_image(height, image, page, width, x, y)
            elif style == "typed":
                try:
                    font_name_req = field.get("font", "helv")
                    font_name = self.get_valid_font(page, font_name_req)
                    font_size = field.get("font_size", 14)
                    page.insert_text((x, y), str(value), fontsize=font_size, fontname=font_name, color=(0, 0, 0))
                    data1 = generate_signature_b64_from_fontname(text=value, font_name=font_name)
                    data = data1.split(",")[1]
                    metadata_key = f"{email}/signatures/{tracking_id}/signatures/{party_id}.json"
                    logger.info(f"typed : {data1}")
                    metadata_dict = {
                        str(party_id): {
                            "style": style,
                            "s3_key": data1
                        }
                    }
                    json_data = json.dumps(metadata_dict).encode("utf-8")

                    s3_upload_bytes(json_data, metadata_key, content_type="application/json")

                except Exception as e:
                    logger.error(f"Failed to insert typed signature text: {e}")
            else:
                font_name = self.get_valid_font(pdf_doc, "helv")
                page.insert_text((x, y), str(value), fontsize=12, fontname=font_name, color=(0, 0, 0))

        elif field_type == "checkbox":
            if value.startswith("data:image"):
                data = value.split(",")[1]
                image_data = base64.b64decode(data)
                image = Image.open(BytesIO(image_data))
                fixed_width, fixed_height = 15, 15
                image = image.resize((fixed_width, fixed_height))

                img_byte_arr = BytesIO()
                image.save(img_byte_arr, format="PNG")

                page.insert_image(
                    fitz.Rect(x, y, x + fixed_width, y + fixed_height),
                    stream=img_byte_arr.getvalue()
                )

        elif field_type == "date":
            self.insert_date_field(field, page, pdf_doc, value, x, y)

        elif field_type == "initial":
            self.insert_typed_signature_text(field, page, value, x, y)

        elif field_type == "dropdown":
            self.insert_typed_signature_text(field, page, value, x, y)

        elif field_type == "attach":
            data = value.split(",")[1]
            image_data = base64.b64decode(data)
            image = Image.open(BytesIO(image_data))
            if image.mode == "RGBA":
                self.insert_transparent_signature(height, image, page, width, x, y)
            else:
                self.insert_flat_signature_image(height, image, page, width, x, y)


        else:
            logger.warning(f"Unknown field type '{field_type}' on page {page_number + 1}")

    def insert_text_field(self, field, page, pdf_doc, value, x, y):
        try:
            font_name_req = field.get("font", "helv")
            font_name = self.get_valid_font(pdf_doc, font_name_req)
            font_size = field.get("font_size", 10)
            page.insert_text((x, y), str(value), fontsize=font_size, fontname=font_name, color=(0, 0, 0))
        except Exception as e:
            logger.error(f"Failed to insert text field: {e}")

    def insert_typed_signature_text(self, field, page, value, x, y):
        try:
            font_name_req = field.get("font", "helv")
            font_name = self.get_valid_font(page, font_name_req)
            font_size = field.get("font_size", 14)
            page.insert_text((x, y), str(value), fontsize=font_size, fontname=font_name, color=(0, 0, 0))
        except Exception as e:
            logger.error(f"Failed to insert typed signature text: {e}")

    def insert_date_field(self, field, page, pdf_doc, value, x, y):
        try:
            font_name_req = field.get("font", "helv")
            font_name = self.get_valid_font(pdf_doc, font_name_req)
            font_size = field.get("font_size", 12)
            page.insert_text((x, y), str(value), fontsize=font_size, fontname=font_name, color=(0, 0, 0))
        except Exception as e:
            logger.error(f"Failed to insert date: {e}")

    def insert_checkbox_image(self, checkbox_value, height, page, width, x, y):
        try:
            checkbox_image_data = base64.b64decode(self.get_checkbox_base64(checkbox_value))
            image = Image.open(BytesIO(checkbox_image_data)).convert("RGB")
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format="PNG")
            page.insert_image(
                fitz.Rect(x, y, x + width, y + height),
                stream=img_byte_arr.getvalue()
            )
            logger.info(f"Inserted {'checked' if checkbox_value else 'unchecked'} checkbox at ({x}, {y})")
        except Exception as e:
            logger.error(f"Failed to render checkbox image: {e}")

    def get_checkbox_base64(self, checkbox_value):
        return (
            "PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3..."
            if checkbox_value else
            "PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3..."
        )

    def insert_flat_signature_image(self, height, image, page, width, x, y):
        try:
            image = image.convert("RGB")
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format="PNG")
            page.insert_image(
                fitz.Rect(x, y - 10, x + width, y + height),
                stream=img_byte_arr.getvalue()
            )
        except Exception as e:
            logger.error(f"Failed to insert flat signature image: {e}")

    def insert_transparent_signature(self, height, image, page, width, x, y):
        """
        Inserts only the visible signature part (transparent PNG) onto the PDF page.
        """
        try:
            # Ensure the image is in RGBA (preserves alpha channel)
            if image.mode != "RGBA":
                image = image.convert("RGBA")

            # Convert image to bytes
            img_bytes = BytesIO()
            image.save(img_bytes, format="PNG")  # PNG preserves transparency
            img_bytes.seek(0)

            # Define rectangle for placement
            rect = fitz.Rect(x, y-30, x + width, y + height)

            # Embed image directly with transparency
            page.insert_image(rect, stream=img_bytes.read(), overlay=True)
        except Exception as e:
            logger.error(f"Failed to insert signature-only image: {e}")