import os
import requests
import pikepdf
import img2pdf
from PIL import Image
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from docling.document_converter import DocumentConverter
from pydantic_ai import Agent
import tempfile
import uuid


app = FastAPI()

# --- Config ---
WEB_SECRET = os.getenv("WEBHOOK_SECRET")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

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
    Compresses PDF or Converts Image -> Compressed PDF.
    Returns path to the final optimized PDF.
    """
    output_path = f"{input_path}_optimized.pdf"
    ext = os.path.splitext(original_filename)[1].lower()

    try:
        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
            # 1. Image -> PDF
            with Image.open(input_path) as img:
                # Convert RGBA to RGB (fix png transparency issues)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')

                # Resize if massive (limit to 2000px width, preserve aspect)
                if img.width > 2000:
                    ratio = 2000 / img.width
                    new_size = (2000, int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

                # Save optimized temporary JPG
                temp_img = f"{input_path}.jpg"
                img.save(temp_img, "JPEG", quality=70, optimize=True)

                # Convert to PDF
                with open(output_path, "wb") as f:
                    f.write(img2pdf.convert(temp_img))

                os.remove(temp_img)

        elif ext == '.pdf':
            # 2. PDF -> Compressed PDF (using Pikepdf)
            with pikepdf.open(input_path) as pdf:
                # Remove unreferenced resources and linearize (fast web view)
                pdf.save(output_path, linearize=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)

        else:
            # Fallback: Just rename/copy if unknown type
            return input_path

        return output_path

    except Exception as e:
        print(f"Compression failed: {e}, using original")
        return input_path

# --- AI & Processing ---
agent = Agent(
    'google:gemini-1.5-flash',
    result_type=InvoiceData,
    system_prompt="Extract invoice data precisely. Return null if field is missing."
)

def process_task(req: ProcessRequest):
    temp_input = None
    final_pdf_path = None
    
    try:
        # 1. Download file securely
        resp = requests.get(req.file_proxy, headers={'x-secret': WEB_SECRET})
        if resp.status_code != 200:
            raise Exception("Download Failed")

        # Create a temporary file to store the downloaded content
        temp_input = f"/tmp/{req.doc_id}_raw{os.path.splitext(req.file_proxy)[-1] or '.pdf'}"
        with open(temp_input, "wb") as f:
            f.write(resp.content)

        # 2. Compress / Standardize the file
        final_pdf_path = compress_and_standardize(temp_input, temp_input)

        # 3. Extract data using Docling and AI
        converter = DocumentConverter()
        result = converter.convert(final_pdf_path)
        markdown = result.document.export_to_markdown()

        # 4. AI Extraction
        ai_result = agent.run_sync(f"Extract from: {markdown[:30000]}")  # Limit context to first 30k chars
        data = ai_result.data

        # 5. Upload FINAL PDF to Drive (stub - implement with google-api-python-client)
        # from utils.gdrive import upload_to_drive
        # drive_id = upload_to_drive(final_pdf_path, f"{data.vendor_name or 'document'}.pdf")
        drive_id = f"fake_drive_id_{uuid.uuid4()}"  # Placeholder

        # 6. Success Callback with PRD-compliant payload
        callback_resp = requests.post(
            f"{req.callback_url}?docId={req.doc_id}",
            headers={'x-secret': WEB_SECRET},
            json={
                "status": "COMPLETED",
                "data": data.model_dump(),
                "drive_file_id": drive_id,
                "error": None
            }
        )
        
        if callback_resp.status_code != 200:
            print(f"Callback failed: {callback_resp.status_code}, {callback_resp.text}")

    except Exception as e:
        print(f"Processing error for {req.doc_id}: {e}")
        # Failure Callback with PRD-compliant payload
        try:
            requests.post(
                f"{req.callback_url}?docId={req.doc_id}",
                headers={'x-secret': WEB_SECRET},
                json={
                    "status": "FAILED", 
                    "error": str(e),
                    "data": None,
                    "drive_file_id": None
                }
            )
        except Exception as callback_error:
            print(f"Failed to send error callback: {callback_error}")
    finally:
        # Clean up temporary files
        if temp_input and os.path.exists(temp_input):
            os.remove(temp_input)
        if final_pdf_path and final_pdf_path != temp_input and os.path.exists(final_pdf_path):
            os.remove(final_pdf_path)

@app.post("/process")
async def process_endpoint(req: ProcessRequest, bg_tasks: BackgroundTasks):
    bg_tasks.add_task(process_task, req)
    return {"status": "queued", "doc_id": req.doc_id}

@app.get("/health")
def health():
    return {"status": "ok"}