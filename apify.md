# 📄 MASTER PRD: Agentic Document Extractor (Apify + Modal + Groq)

**Version:** 2.0 (Final - Pure JSON)
**Status:** Ready for Build
**Target Stack:** Apify (Controller) + Modal (GPU OCR) + Groq (LPU Extraction)

## 1. Project Overview

We are building a **Universal Document Extraction Actor** on Apify.

- **Core Function:** Takes a PDF/Image URL -> Returns validated, structured JSON.
- **Key Differentiator:** "Self-Correcting." It doesn't just read; it validates math (e.g., `Sum(Lines) == Total`) and logic. If validation fails, the Agent retries the extraction with "hints."
- **Philosophy:** "Unix Style" - Do one thing well. Return clean JSON so users can pipe it into n8n, Zapier, or their own DBs via Webhooks.

------

## 2. File Structure

The project must follow this exact structure to work on Apify.

```
textapify-agentic-actor/
├── .actor/
│   ├── input_schema.json    # Defines UI inputs in Apify Console
│   └── Dockerfile           # Defines container environment
├── src/
│   ├── main.py              # Entry point (LangGraph Orchestrator)
│   ├── models.py            # Pydantic Data Models
│   ├── modal_client.py      # Modal API Wrapper
│   └── utils.py             # Math validation helpers
├── modal_service/
│   └── ocr_app.py           # The Modal.com GPU Script (Deployed separately)
├── requirements.txt         # Python dependencies
└── README.md
```

------

## 3. Data Models (`src/models.py`)

**Instruction:** Copy strictly. This defines the output format.

```
pythonfrom typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class LineItem(BaseModel):
    description: str = Field(default="", description="Item name or description")
    quantity: float = Field(default=0.0, description="Count/Qty")
    unit_price: float = Field(default=0.0, description="Price per unit")
    total: float = Field(default=0.0, description="Line total")

class ExtractedData(BaseModel):
    # Core Fields
    vendor_name: Optional[str] = Field(None, description="Name of the supplier/vendor")
    invoice_date: Optional[str] = Field(None, description="YYYY-MM-DD format")
    invoice_number: Optional[str] = Field(None, description="Invoice ID")
    currency: str = Field(default="USD", description="Currency Code (USD, EUR)")
    tax_amount: float = Field(default=0.0, description="Total Tax/VAT")
    total_amount: float = Field(default=0.0, description="Final Total Due")
    line_items: List[LineItem] = Field(default_factory=list)
    
    # Dynamic Fields (for custom schemas)
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # Metadata for Agent
    validation_warnings: List[str] = Field(default_factory=list)
    is_valid: bool = Field(default=True)
```

------

## 4. Input Schema (`.actor/input_schema.json`)

**Instruction:** This defines the UI in Apify.

```
json{
    "title": "Agentic Document Extractor",
    "type": "object",
    "schemaVersion": 1,
    "properties": {
        "pdf_url": {
            "type": "string",
            "title": "Document URL",
            "description": "Direct link to PDF or Image.",
            "editor": "textfield"
        },
        "fields_to_extract": {
            "type": "array",
            "title": "Custom Fields (Optional)",
            "description": "List of specific fields to extract (e.g. 'po_number', 'shipping_address').",
            "editor": "stringList",
            "default": []
        },
        "modal_url": {
            "type": "string",
            "title": "Modal OCR Endpoint",
            "description": "URL of your deployed Modal function (e.g. https://xyz.modal.run). If empty, uses local fallback (slower).",
            "editor": "textfield",
            "isSecret": true
        },
        "groq_api_key": {
            "type": "string",
            "title": "Groq API Key",
            "editor": "textfield",
            "isSecret": true
        }
    },
    "required": ["pdf_url", "groq_api_key"]
}
```

------

## 5. Logic Implementation

## A. The OCR Service (`modal_service/ocr_app.py`)

**Instruction:** This runs on Modal.com. It scales to zero when not used.

```
pythonimport modal

app = modal.App("granite-docling-ocr")
image = modal.Image.debian_slim().pip_install("docling", "docling-core")

@app.function(
    image=image,
    gpu="T4",  # Cheap, fast GPU
    timeout=120,
    container_idle_timeout=300
)
@modal.web_endpoint(method="POST")
def process_pdf(data: dict):
    from docling.document_converter import DocumentConverter
    
    url = data.get("pdf_url")
    if not url:
        return {"error": "No URL provided"}, 400
    
    print(f"Processing: {url}")
    converter = DocumentConverter() # Loads standard models
    result = converter.convert(url)
    markdown = result.document.export_to_markdown()
    
    return {"markdown": markdown, "status": "success"}
```

## B. The Orchestrator (`src/main.py`)

**Instruction:** Implement `LangGraph` State Machine.

**State Definition:**

```
pythonclass AgentState(TypedDict):
    pdf_url: str
    custom_fields: List[str]
    markdown: Optional[str]
    extracted_json: Optional[dict]
    validation_errors: List[str]
    retry_count: int
```

**Nodes Logic:**

1. **`ingest_node`**:
   - Input: `state['pdf_url']`.
   - Logic: POST to `MODAL_URL` (if exists) OR run `docling` locally.
   - Output: `markdown`.
2. **`extract_node`**:
   - Input: `markdown`, `custom_fields`.
   - Logic: Call Groq (`llama-3.3-70b-versatile` or `openai/gpt-oss-20b`).
   - Prompt: "Extract JSON. Schema: InvoiceData + {custom_fields}. Context: {markdown}. Valid JSON only."
   - **Self-Correction:** If `state['validation_errors']` is not empty, append: "CRITICAL: Previous attempt failed validation with errors: {errors}. Fix these specific issues."
   - Output: `extracted_json`.
3. **`validate_node`**:
   - Input: `extracted_json`.
   - Logic (Math Check):
     - Calculate `sum_lines = sum(item['total'] for item in line_items)`.
     - Check `abs(sum_lines - total_amount) < 0.05`.
     - If fail -> Add error "Math Mismatch: Sum of lines {sum_lines} != Total {total_amount}".
   - Logic (Null Check): Verify `vendor_name` and `total_amount` are not null.
   - Output: `validation_errors`.
4. **`router`**:
   - If `validation_errors` is EMPTY -> Go to `save`.
   - If `retry_count` > 2 -> Go to `save` (Stop looping, return best effort with `is_valid=False`).
   - Else -> Go to `extract` (Retry).
5. **`save_node`**:
   - Logic: `Actor.push_data(state['extracted_json'])`.

------

## 6. Dockerfile (`.actor/Dockerfile`)

**Instruction:** Use the official Apify Python base.

```
textFROM apify/actor-python-3.11

# Install system dependencies for local Docling fallback
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "-m", "src.main"]
```

## 7. Requirements (`requirements.txt`)

```
textapify-client
langgraph
langchain-core
langchain-groq
pydantic
httpx
docling # Only for fallback
python-dotenv
```

------

## 8. Deployment SOP

1. **Deploy Modal:**
   - Run: `modal deploy modal_service/ocr_app.py`
   - Copy the URL (e.g., `https://username--granite-docling-ocr-process-pdf.modal.run`).
2. **Configure Apify:**
   - Create Actor.
   - Set `modal_url` (Secret) = [Your Modal URL].
   - Set `groq_api_key` (Secret) = [Your Groq Key].
3. **Run Test:**
   - Input: A complex PDF invoice URL.
   - Verify: Check the "Output" tab for clean JSON.
   - Verify: Check logs to see if "Math Validation" passed or triggered a retry.

------

**END OF PRD**
