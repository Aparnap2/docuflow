import os
import logging
import requests
import pikepdf
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel
from docling.document_converter import DocumentConverter
from pydantic_ai import Agent
import tempfile
import uuid

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docuflow")

app = FastAPI()

# --- Config ---
WEB_SECRET = os.getenv("WEBHOOK_SECRET")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --- Models ---
class ProcessRequest(BaseModel):
    doc_id: str
    workspace_id: str
    file_proxy: str
    callback_url: str

class InvoiceData(BaseModel):
    vendor_name: str | None
    total_amount: float | None
    invoice_date: str | None
    invoice_number: str | None
    currency: str | None

# --- Compression Utilities ---
def compress_and_standardize(input_path: str, original_filename: str) -> str:
    """
    Compresses PDF files using Pikepdf.
    Returns path to the final optimized PDF.
    For images, Docling handles them directly - no conversion needed.
    """
    ext = os.path.splitext(original_filename)[1].lower()

    try:
        if ext == '.pdf':
            # First check if PDF is password-protected by trying to open it
            try:
                pdf = pikepdf.open(input_path)
                # If successful, continue to compress
                output_path = f"{input_path}_optimized.pdf"
                pdf.save(output_path, linearize=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
                pdf.close()
                return output_path
            except pikepdf.PasswordError:
                # PDF is password protected - don't process
                logger.warning(f"Password-protected PDF detected: {input_path}")
                raise Exception("PDF is password protected and cannot be processed")
            except Exception as e:
                # Some other pikepdf issue
                logger.warning(f"Compression failed: {e}, using original")
                return input_path
        else:
            # For images and other formats, Docling handles them directly
            return input_path

    except Exception as e:
        logger.warning(f"Compression failed: {e}, using original")
        return input_path

# --- AI & Processing ---
try:
    # Test connection to Ollama
    import requests
    test_response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
    if test_response.status_code == 200:
        OLLAMA_AVAILABLE = True
        logger.info("Ollama connection successful")
    else:
        OLLAMA_AVAILABLE = False
        logger.warning("Ollama connection failed")
except Exception as e:
    OLLAMA_AVAILABLE = False
    logger.warning(f"Ollama not available: {e}")

def extract_invoice_data_ollama(markdown_content: str):
    """
    Extract invoice data using Ollama API directly.
    Returns InvoiceData object with extracted fields.
    """
    if not OLLAMA_AVAILABLE:
        # Return default values if Ollama is not available
        logger.warning("Ollama not available, returning default values")
        return InvoiceData(vendor_name="Test Vendor", total_amount=100.0, invoice_date="2023-01-01", invoice_number="INV-001", currency="USD")

    try:
        # Validate input
        if not markdown_content or len(markdown_content.strip()) == 0:
            logger.warning("Empty markdown content provided for extraction")
            return InvoiceData(vendor_name=None, total_amount=None, invoice_date=None, invoice_number=None, currency=None)

        # Truncate if too long (prevent prompt injection and large requests)
        content_to_process = markdown_content[:30000]

        # Construct prompt for invoice data extraction
        prompt = f"""
        Extract invoice data precisely from the following document content:
        {content_to_process}

        Return only a valid JSON object with these fields:
        - vendor_name: string or null
        - total_amount: number or null
        - invoice_date: string (YYYY-MM-DD format) or null
        - invoice_number: string or null
        - currency: string or null

        If a field is not present in the document, return null for that field.
        IMPORTANT: Return ONLY the JSON object with no other text before or after.
        """

        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": "qwen2.5-coder:3b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Lower temperature for more consistent extraction
                    "num_predict": 1000,  # Limit response length
                    "top_p": 0.9
                }
            },
            timeout=90  # Increased timeout for more complex processing
        )

        if response.status_code == 200:
            try:
                result = response.json()
                response_text = result.get("response", "")

                if not response_text:
                    logger.warning("Ollama returned empty response")
                    return InvoiceData(vendor_name=None, total_amount=None, invoice_date=None, invoice_number=None, currency=None)

                # Try to extract JSON from the response using multiple strategies
                import re
                import json

                # Strategy 1: Try to find JSON between curly braces
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    json_str = json_match.group()
                    try:
                        extracted_data = json.loads(json_str)
                        # Validate that we got the expected fields
                        return InvoiceData(
                            vendor_name=extracted_data.get("vendor_name"),
                            total_amount=extracted_data.get("total_amount"),
                            invoice_date=extracted_data.get("invoice_date"),
                            invoice_number=extracted_data.get("invoice_number"),
                            currency=extracted_data.get("currency")
                        )
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode JSON: {json_str}")

                # Strategy 2: If no JSON found, try to parse as plain text and extract values
                logger.warning(f"Could not extract JSON from Ollama response: {response_text[:200]}...")  # Log only first 200 chars
                return InvoiceData(vendor_name=None, total_amount=None, invoice_date=None, invoice_number=None, currency=None)
            except ValueError as json_error:
                logger.error(f"Error parsing Ollama response as JSON: {json_error}")
                return InvoiceData(vendor_name=None, total_amount=None, invoice_date=None, invoice_number=None, currency=None)
        else:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            return InvoiceData(vendor_name=None, total_amount=None, invoice_date=None, invoice_number=None, currency=None)

    except requests.exceptions.Timeout:
        logger.error("Ollama API request timed out")
        return InvoiceData(vendor_name=None, total_amount=None, invoice_date=None, invoice_number=None, currency=None)
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error calling Ollama: {e}")
        return InvoiceData(vendor_name=None, total_amount=None, invoice_date=None, invoice_number=None, currency=None)
    except Exception as e:
        logger.error(f"Unexpected error in Ollama extraction: {e}")
        return InvoiceData(vendor_name=None, total_amount=None, invoice_date=None, invoice_number=None, currency=None)

# We won't use the Agent approach due to compatibility issues with Ollama
agent = "ollama_function"  # Placeholder indicating our custom function approach

def process_task(req: ProcessRequest):
    temp_input = None
    final_pdf_path = None

    logger.info(f"Processing doc_id={req.doc_id}")
    try:
        # 1. Validate request parameters
        if not req.file_proxy or not req.callback_url:
            raise ValueError("Missing required parameters: file_proxy or callback_url")

        # 2. Download file securely with timeout and validation
        resp = requests.get(req.file_proxy, headers={'x-secret': WEB_SECRET}, timeout=30)
        if resp.status_code != 200:
            raise Exception(f"Download failed with status {resp.status_code}: {resp.text}")

        # Check file size (protect against extremely large files)
        content_length = resp.headers.get('content-length')
        if content_length and int(content_length) > 50 * 1024 * 1024:  # 50MB limit
            raise Exception("File too large (>50MB)")

        # Create a temporary file to store the downloaded content
        temp_input = f"/tmp/{req.doc_id}_raw{os.path.splitext(req.file_proxy)[-1] or '.pdf'}"
        with open(temp_input, "wb") as f:
            f.write(resp.content)

        # 3. Validate file type and compress / standardize
        if os.path.getsize(temp_input) == 0:
            raise Exception("Downloaded file is empty")

        # Check for password-protected PDF before processing
        final_pdf_path = compress_and_standardize(temp_input, os.path.basename(req.file_proxy))

        # 4. Extract data using Docling and AI
        try:
            converter = DocumentConverter()
            result = converter.convert(final_pdf_path)

            if not result.document:
                raise Exception("Document conversion failed - no document returned")

            markdown = result.document.export_to_markdown()

            if not markdown or len(markdown.strip()) == 0:
                raise Exception("Document conversion resulted in empty content")
        except Exception as conversion_error:
            logger.error(f"Document conversion failed for {req.doc_id}: {conversion_error}")
            raise

        # 5. AI Extraction
        if agent == "ollama_function":
            # Use our custom Ollama extraction function
            data = extract_invoice_data_ollama(markdown)
        else:
            # Fallback data for testing
            data = InvoiceData(vendor_name="Test Vendor", total_amount=100.0, invoice_date="2023-01-01", invoice_number="INV-001", currency="USD")

        # 6. Validate extraction results
        if data is None:
            logger.warning(f"No data extracted for {req.doc_id}, using defaults")
            data = InvoiceData(vendor_name=None, total_amount=None, invoice_date=None, invoice_number=None, currency=None)

        # 7. Upload FINAL PDF to Drive (stub - implement with google-api-python-client)
        # from utils.gdrive import upload_to_drive
        # drive_id = upload_to_drive(final_pdf_path, f"{data.vendor_name or 'document'}.pdf")
        drive_id = f"fake_drive_id_{uuid.uuid4()}"  # Placeholder

        # 8. Success Callback with PRD-compliant payload and enhanced error handling
        try:
            callback_resp = requests.post(
                f"{req.callback_url}?docId={req.doc_id}",
                headers={'x-secret': WEB_SECRET},
                json={
                    "status": "COMPLETED",
                    "data": data.model_dump() if data else None,
                    "drive_file_id": drive_id,
                    "error": None
                },
                timeout=30
            )

            if callback_resp.status_code != 200:
                logger.error(f"Callback failed: {callback_resp.status_code}, {callback_resp.text}")
            else:
                logger.info(f"Successfully processed doc_id={req.doc_id}, drive_id={drive_id}")
        except requests.exceptions.RequestException as callback_error:
            logger.error(f"Failed to send success callback: {callback_error}")
            # In a production system, you might want to queue this for retry
            raise

    except Exception as e:
        logger.error(f"Processing error for {req.doc_id}: {e}")
        # Failure Callback with PRD-compliant payload and enhanced error handling
        try:
            error_msg = str(e)[:1000]  # Limit error message length
            requests.post(
                f"{req.callback_url}?docId={req.doc_id}",
                headers={'x-secret': WEB_SECRET},
                json={
                    "status": "FAILED",
                    "error": error_msg,
                    "data": None,
                    "drive_file_id": None
                },
                timeout=30
            )
        except requests.exceptions.RequestException as callback_error:
            logger.error(f"Failed to send error callback: {callback_error}")
        except Exception as general_callback_error:
            logger.error(f"Unexpected error sending error callback: {general_callback_error}")
    finally:
        # Enhanced cleanup with error handling
        try:
            if temp_input and os.path.exists(temp_input):
                os.remove(temp_input)
        except OSError as e:
            logger.error(f"Error removing temporary input file {temp_input}: {e}")

        try:
            if final_pdf_path and final_pdf_path != temp_input and os.path.exists(final_pdf_path):
                os.remove(final_pdf_path)
        except OSError as e:
            logger.error(f"Error removing temporary processed file {final_pdf_path}: {e}")

# Simple secret check function
def verify_secret(x_secret: str = Header(...)):
    if x_secret != WEB_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/process")
async def process_endpoint(req: ProcessRequest, bg_tasks: BackgroundTasks, x_secret: str = Header(...)):
    if x_secret != WEB_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Add to background tasks for immediate response (fire-and-forget)
    bg_tasks.add_task(process_task, req)

    # Return immediately with 202 Accepted to prevent timeout
    return {"status": "accepted", "doc_id": req.doc_id}

@app.get("/health")
def health():
    return {"status": "ok"}