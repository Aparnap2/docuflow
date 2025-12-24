from fastapi import FastAPI, Request, HTTPException
from docling.document_converter import DocumentConverter
import langextract as lx
from langextract.data import ExampleData, Extraction
import textwrap
import requests
import json
import tempfile
import os
import boto3

app = FastAPI()
ENGINE_SECRET = os.getenv("ENGINE_SECRET")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET = "structurize-inbox"
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "https://<account>.r2.cloudflarestorage.com")

def get_s3_client():
    """Create S3 client lazily to avoid import-time errors"""
    return boto3.client(
        's3',
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        endpoint_url=R2_ENDPOINT
    )

FREIGHT_PROMPT = textwrap.dedent("""\
    Extract exactly these fields from the Bill of Lading or Carrier Invoice:
    - PRO Number (typically in format like PRO-XXXX or similar identifier)
    - Carrier Name (transportation company name)
    - Origin Zip Code (starting location ZIP)
    - Destination Zip Code (ending location ZIP)
    - Billable Weight (in lbs, usually near 'Weight' or 'Wt')
    - Line Haul Rate (base transportation rate)
    - Fuel Surcharge (additional fuel cost)
    - Total Amount (final invoice amount)

    Point to exact text locations. Do not guess.""")

@app.post("/process")
async def process_job(request: Request):
    if request.headers.get("x-secret") != ENGINE_SECRET:
        raise HTTPException(401, "Unauthorized")

    data = await request.json()
    r2_key = data.get("r2_key")
    job_id = data.get("job_id")

    # Use S3 client to fetch the document from R2
    s3_client = get_s3_client()
    response = s3_client.get_object(Bucket=R2_BUCKET, Key=r2_key)
    pdf_content = response['Body'].read()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_content)
        temp_pdf_path = f.name

    try:
        # Get model configuration from environment variables
        model_id = os.getenv("LANGEXTRACT_MODEL_ID", "gemini-2.5-flash")
        extraction_passes = int(os.getenv("LANGEXTRACT_PASSES", "2"))
        max_workers = int(os.getenv("LANGEXTRACT_MAX_WORKERS", "4"))

        lang_result = lx.extract(
            text_or_documents=temp_pdf_path,
            prompt_description=FREIGHT_PROMPT,
            model_id=model_id,
            extraction_passes=extraction_passes,
            max_workers=max_workers
        )
        
        html_viz = lx.visualize([lang_result])
        viz_key = f"proof/{data.get('job_id')}.html"
        
        get_s3_client().put_object(
            Bucket=R2_BUCKET,
            Key=viz_key,
            Body=html_viz.data,
            ContentType="text/html"
        )
        
        R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://pub-<hash>.r2.dev")
        proof_url = f"{R2_PUBLIC_URL}/{viz_key}"
        
        converter = DocumentConverter()
        doc_result = converter.convert(temp_pdf_path)
        
        line_items = []
        if doc_result.document.tables:
            table = doc_result.document.tables[0]
            line_items = table.to_dict('records')
        
        header_data = {
            "pro_number": _find_extraction(lang_result, "PRO Number"),
            "carrier": _find_extraction(lang_result, "Carrier Name"),
            "origin_zip": _find_extraction(lang_result, "Origin Zip Code"),
            "dest_zip": _find_extraction(lang_result, "Destination Zip Code"),
            "weight": _find_extraction(lang_result, "Billable Weight"),
            "line_haul_rate": _find_extraction(lang_result, "Line Haul Rate"),
            "fuel_surcharge": _find_extraction(lang_result, "Fuel Surcharge"),
            "total": _find_extraction(lang_result, "Total Amount")
        }

        structured_data = {
            "header": header_data,
            # Add flat keys for compatibility with sync worker and audit function
            "pro_number": header_data["pro_number"]["value"] if header_data["pro_number"] else None,
            "carrier": header_data["carrier"]["value"] if header_data["carrier"] else None,
            "origin_zip": header_data["origin_zip"]["value"] if header_data["origin_zip"] else None,
            "dest_zip": header_data["dest_zip"]["value"] if header_data["dest_zip"] else None,
            "weight": header_data["weight"]["value"] if header_data["weight"] else None,
            "line_haul_rate": header_data["line_haul_rate"]["value"] if header_data["line_haul_rate"] else None,
            "fuel_surcharge": header_data["fuel_surcharge"]["value"] if header_data["fuel_surcharge"] else None,
            "total": header_data["total"]["value"] if header_data["total"] else None,
            "line_items": line_items,
            "visual_proof_url": proof_url,
            "markdown": doc_result.document.export_to_markdown()
        }
        
        return structured_data
        
    finally:
        if os.path.exists(temp_pdf_path):
            os.unlink(temp_pdf_path)

def _find_extraction(result, field_name):
    for doc in result.documents:
        for extraction in doc.extractions:
            # The extraction_class might contain the field name
            if hasattr(extraction, 'extraction_class') and field_name in extraction.extraction_class:
                return {
                    "value": extraction.extraction_text.strip(),
                    "confidence": getattr(extraction, 'score', 1.0) if hasattr(extraction, 'score') else 1.0,
                    "span": getattr(extraction, 'span', None)
                }
            # Also check if extraction_class is a property that contains field name
            elif hasattr(extraction, 'extraction_class') and hasattr(extraction.extraction_class, 'name') and field_name in extraction.extraction_class.name:
                return {
                    "value": extraction.extraction_text.strip(),
                    "confidence": getattr(extraction, 'score', 1.0) if hasattr(extraction, 'score') else 1.0,
                    "span": getattr(extraction, 'span', None)
                }
            # Fallback: check if the field name is mentioned in the extraction text
            elif field_name.lower() in extraction.extraction_class.lower() if hasattr(extraction, 'extraction_class') and extraction.extraction_class else False:
                return {
                    "value": extraction.extraction_text.strip(),
                    "confidence": getattr(extraction, 'score', 1.0) if hasattr(extraction, 'score') else 1.0,
                    "span": getattr(extraction, 'span', None)
                }
    return None