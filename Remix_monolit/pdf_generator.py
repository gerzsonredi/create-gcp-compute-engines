# -*- coding: utf-8 -*-
"""pdf_generator.py - batch PDF creation that uses a fixed background template

This module keeps the *same* public entry-point that your Flask route already
imports - ``create_batch_report_from_image_groups`` - so you can drop it in as a
replacement without touching the rest of the pipeline.

Key changes
-----------
*   **Background template** - every page starts from the single page contained
    in ``background.pdf`` (1920 x 1080 pt) and we draw an overlay on top using
    ReportLab, then merge it with `pdfrw`.
*   **Only garments with measurements** (``result["measurements"]["success"]``)
    are included; others are silently skipped.
*   **Images** - the *Original* and *Measured* images are rendered into the
    large white rectangles of the template, keeping aspect-ratio.
*   **Text** - the SKU goes into the header box; only *Length* and *Width* (in
    pixels) are written into the measurements panel.

Dependencies: ``pip install reportlab pdfrw pillow requests``.
The module will raise a helpful error if the template is missing.
"""

import io
import os
from datetime import datetime
from urllib.parse import urlparse

import requests
from PIL import Image
import numpy as np
import boto3
import json
from pdfrw import PdfReader, PdfWriter, PageMerge, PdfDict
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Location of the PDF template that contains the background. Override with the
# REPORT_TEMPLATE_PATH env-var if you keep the file elsewhere inside the
# container.
BACKGROUND_PATH = os.getenv("REPORT_TEMPLATE_PATH", "/app/background.pdf")

# The background template was designed at 1920 x 1080 px (landscape).
PAGE_WIDTH = 1920
PAGE_HEIGHT = 1080

# ---- Coordinate system (origin bottom-left) ----
#   You can fine-tune these constants if the boxes ever move in the template.
SKU_W, SKU_H = 500, 150
SKU_X = (PAGE_WIDTH - SKU_W) / 2
SKU_Y = PAGE_HEIGHT - SKU_H - 30

ORIG_X, ORIG_Y = 120, 80
ORIG_W, ORIG_H = 540, 780

MEAS_X = ORIG_X + ORIG_W + 160
MEAS_Y, MEAS_W, MEAS_H = ORIG_Y, 540, 780

ORIG_W, ORIG_H = int(540 * 0.8), int(780 * 0.8)
MEAS_W, MEAS_H = int(540 * 0.8), int(780 * 0.8)

TEXT_X = MEAS_X + MEAS_W + 200
TEXT_Y_START = ORIG_Y + MEAS_H + 10
TEXT_LINE_H = 70

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("LibreBaskerville",        "fonts/Libre_Baskerville/LibreBaskerville-Regular.ttf"))
pdfmetrics.registerFont(TTFont("LibreBaskerville-Bold",   "fonts/Libre_Baskerville/LibreBaskerville-Bold.ttf"))

FONT      = "LibreBaskerville"
FONT_BOLD = "LibreBaskerville-Bold"

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _download_image(url: str):
    """Download *url* and return a ``PIL.Image`` (or ``None`` on failure)."""
    if not url:
        return None
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img
    except Exception:
        return None


def _draw_image(can: canvas.Canvas, img: Image.Image, x: int, y: int, box_w: int, box_h: int):
    """Draw *img* inside the rectangle (*x*, *y*, *box_w*, *box_h*) preserving
    aspect ratio and centred."""
    if img is None:
        return
    w, h = img.size
    scale = min(box_w / w, box_h / h)
    draw_w, draw_h = w * scale, h * scale
    draw_x = x + (box_w - draw_w) / 2
    draw_y = y + (box_h - draw_h) / 2
    can.drawImage(ImageReader(img), draw_x, draw_y, draw_w, draw_h, preserveAspectRatio=True, mask="auto")

def get_image_from_link(public_url):
    """
    Helper function that loads image from public_url or private S3 URL
    Returns numpy array
    """
    print("get_image_from_link function called")
    print(f"{public_url=}")
    if not public_url:
        return None
    try:
        # Check if it's an S3 URL that might require credentials
        if 's3' in public_url and 'amazonaws.com' in public_url:
            return _get_image_from_s3_url(public_url)
        else:
            r = requests.get(public_url, timeout=10)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            return img
            return np.array(img)
    except Exception as e:
        print("ERROR while loading image ")
        print(e)
        return None 
    
def _get_image_from_s3_url(s3_url):
    """
    Helper function to get image from S3 URL using AWS credentials
    """
    try:
        # Parse the S3 URL to extract bucket and key
        # Format: https://bucket-name.s3.region.amazonaws.com/key
        # or: https://s3.region.amazonaws.com/bucket-name/key
        
        parsed_url = urlparse(s3_url)
        
        if parsed_url.hostname.startswith('s3.') or parsed_url.hostname.endswith('.amazonaws.com'):
            # Extract bucket and key from URL
            if parsed_url.hostname.endswith('.s3.amazonaws.com') or '.s3.' in parsed_url.hostname:
                # Format: bucket-name.s3.region.amazonaws.com
                bucket_name = parsed_url.hostname.split('.s3.')[0]
                key = parsed_url.path.lstrip('/')
            else:
                # Format: s3.region.amazonaws.com/bucket-name/key
                path_parts = parsed_url.path.lstrip('/').split('/', 1)
                bucket_name = path_parts[0]
                key = path_parts[1] if len(path_parts) > 1 else ''
        else:
            raise ValueError(f"Unrecognized S3 URL format: {s3_url}")
        
        AWS_ACCESS_KEY_ID = os.getenv("ACCES_KEY_ARTIFACTS", "")
        AWS_SECRET_ACCESS_KEY = os.getenv("SECRET_KEY_ARTIFACTS", "")
        REGION = os.getenv("REGION", "")
        
        session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=REGION
        )
        
        s3_client = session.client('s3')
        
        # Get the object from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        image_data = response['Body'].read()
        
        # Convert to PIL Image and then numpy array
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        return img
        return np.array(img)
        
    except Exception as e:
        print(f"ERROR while loading image from S3: {e}")
        return None

# ---------------------------------------------------------------------------
# Page builder - turns one *analysis result* into a PDF page
# ---------------------------------------------------------------------------

class _TemplatePageBuilder:
    """Internal helper that draws one garment onto the template page."""

    def __init__(self, background_page):
        self._bg_page = background_page
        print(f"DEBUG: MediaBox = {self._bg_page.MediaBox}")
        print(f"DEBUG: MediaBox type = {type(self._bg_page.MediaBox)}")
    
        # Handle case where MediaBox might be malformed
        try:
            mediabox = self._bg_page.MediaBox
            if isinstance(mediabox, (list, tuple)) and len(mediabox) >= 4:
                self._w = float(mediabox[2])
                self._h = float(mediabox[3])
            else:
                # Fallback to default page size
                print(f"WARNING: Invalid MediaBox {mediabox}, using default page size")
                self._w = PAGE_WIDTH
                self._h = PAGE_HEIGHT
        except (TypeError, IndexError, AttributeError) as e:
            print(f"ERROR: Failed to read MediaBox: {e}")
            self._w = PAGE_WIDTH
            self._h = PAGE_HEIGHT

    def build_page(self, garment: dict):
        """Return a **new** pdfrw page, ready to be added to the output."""
        # Measurements
        meas = garment["measurements"]["measurements"]
        length_px = meas.get("length")
        width_px = meas.get("width")

        # Overlay canvas (same size as background)
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(self._w, self._h))

        # SKU field
        sku_val = str(garment.get("sku", ""))
        can.setFont(FONT_BOLD, 40)
        can.drawCentredString(self._w / 2 + 120, SKU_Y + SKU_H / 2 - 18, sku_val)

        # Images
        orig_img = get_image_from_link(garment.get("original_image"))
        measured_url = garment["measurements"].get("url") or ""
        measured_img = get_image_from_link(measured_url)
        if measured_img is None:
            measured_img = orig_img

        _draw_image(can, orig_img, ORIG_X, ORIG_Y, ORIG_W, ORIG_H)
        _draw_image(can, measured_img, MEAS_X, MEAS_Y, MEAS_W, MEAS_H)

        # Measurements text block
        # can.setFont(FONT_BOLD, 28)
        # can.drawString(TEXT_X, TEXT_Y_START, "Measurements")
        can.setFont(FONT, 38)
        ty = TEXT_Y_START - TEXT_LINE_H
        if length_px is not None:
            can.drawString(TEXT_X, ty, f"Length: {length_px:.1f} px")
            ty -= TEXT_LINE_H
        if width_px is not None:
            can.drawString(TEXT_X, ty, f"Width:  {width_px:.1f} px")

        can.save()
        packet.seek(0)
        overlay = PdfReader(packet).pages[0]

        # Create a new page by merging overlay onto the background page
        # Instead of cloning, we create a new page from the background

        
        # Create a new page with the same dimensions as the background
        page = PdfDict()
        page.Type = self._bg_page.Type
        page.MediaBox = self._bg_page.MediaBox
        page.Resources = self._bg_page.Resources
        page.Contents = self._bg_page.Contents
        
        # Merge the overlay onto the new page
        PageMerge(page).add(overlay).render()
        return page

# ---------------------------------------------------------------------------
# Report builder - loops over garments and writes the final PDF
# ---------------------------------------------------------------------------

class _BatchReportBuilder: 
    def __init__(self, template_path: str):
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"Background PDF template not found at '{template_path}'.")
        self._bg_page = PdfReader(template_path).pages[0]
        self._page_builder = _TemplatePageBuilder(self._bg_page)

    def build(self, garments: list, output_path: str):
        writer = PdfWriter()
        try:
            for g in garments:
                try:
                    if 'measurements' not in g:
                        continue
                    if not (g.get("measurements") and g["measurements"].get("success")):
                        # Skip garments without measurements
                        continue
                    writer.addpage(self._page_builder.build_page(g))
                except Exception as e:
                    print("Error while building page!")
                    print(str(e))
                    continue
            writer.write(output_path)
            return output_path
        except Exception as e:
            print("Unexpected error")
            print(str(e))
            return ""
# ---------------------------------------------------------------------------
# Analysis phase - identical public behaviour to the previous script
# ---------------------------------------------------------------------------

class _AnalysisProcessor:
    """Calls the /batch-analysis endpoint for every garment group."""

    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url.rstrip("/")

    def _call_api(self, image_urls: list):
        payload = {
            'image_url': image_urls[0],  # Primary image
            'additional_image_urls': image_urls[1:] if len(image_urls) > 1 else []  # Additional images
        }
        try:
            print(f"Calling API with payload: {json.dumps(payload, indent=2)}")
            response = requests.post(
                f"{self.api_base_url}/full-analysis",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=600  # 10 minutes timeout for full analysis
            )
            
            response.raise_for_status()
            result = response.json()
            
            print(f"API call successful for {len(image_urls)} images")
            return result
        
        except requests.exceptions.RequestException as e:
            print(f"API call failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                    print(f"Error details: {json.dumps(error_details, indent=2)}")
                except:
                    print(f"Error response: {e.response.text}")
            return None

    def process(self, garment_groups: list):
        results = []
        for idx, urls in enumerate(garment_groups, start=1):
            print(f"\nProcessing garment {idx}/{len(garment_groups)}")
            print(f"Images: {urls}")
            res = self._call_api(urls)
            if res and res.get("measurements", {}).get("success"):
                res.setdefault("sku", self.get_sku(urls[0]))
                results.append(res)
        return results

    @staticmethod
    def get_sku(url: str):
        # Fallback - derive "SKU" from the file name in the primary URL
        return os.path.splitext(os.path.basename(urlparse(url).path))[0].split('-')[-1][:-1]

# ---------------------------------------------------------------------------
# PUBLIC ENTRY POINT - unchanged function signature for the Flask route
# ---------------------------------------------------------------------------

def create_batch_report_from_image_groups(
    garment_groups: list,
    output_filename: str = "",
    api_base_url: str = "http://localhost:5000",
    template_path: str = BACKGROUND_PATH,
):
    """Create a PDF batch report; usable exactly as before.

    Parameters
    ----------
    garment_groups
        ``[["img1.jpg"], ["front.jpg", "back.jpg"], ...]``
    output_filename
        Path inside */app/reports/*. If omitted a timestamped name is used.
    api_base_url
        Base URL where your *batch-analysis* endpoint is hosted.
    template_path
        Path to the *background.pdf* template (optional override).
    """

    # 1. Figure out output path
    if not output_filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"batch_report_{ts}.pdf"

    if not output_filename.startswith("/app/reports/"):
        output_filename = f"/app/reports/{os.path.basename(output_filename)}"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    # 2. Analyse
    processor = _AnalysisProcessor(api_base_url)
    analysis_results = processor.process(garment_groups)

    # 3. Build PDF
    builder = _BatchReportBuilder(template_path)
    return builder.build(analysis_results, output_filename)

# ---------------------------------------------------------------------------
# CLI helper (debugging) -----------------------------------------------------
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SAMPLE = [[
        "https://media.remix.eu/files/20-2025/Majki-kas-pantalon-Samsoe---Samsoe-132036343b.jpg"
    ]]

    pdf_path = create_batch_report_from_image_groups(
        SAMPLE,
        output_filename="/app/reports/debug_batch_report.pdf",
        api_base_url="http://localhost:5000",
    )
    print("Report written to", pdf_path)
