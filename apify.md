# 📑 Project: Agentic OCR Service (DeepSeek + Docling)

**Version:** 1.0 (Production Ready)
**Date:** December 29, 2025

## 1. 🎯 Executive Summary

A high-performance, cost-efficient OCR API that converts complex PDF documents (invoices, financial tables) into structured JSON. It leverages a **Hybrid Architecture**:

- **Speed Layer:** Granite-Docling (CPU/Light GPU) for fast, standard documents.
- **Power Layer:** DeepSeek-OCR (GPU) for complex, messy, or dense tables (Fallback).
- **Intelligence Layer:** Llama 3 (Groq/Ollama) for final data extraction and cleaning.

------

## 2. 🏗️ System Architecture & Workflow

## 2.1 The "Happy Path" Flow

1. **Input:** User POSTs a PDF URL to `/extract`.
2. **Gatekeeper:** API Gateway checks Redis Cache (Key: `hash(pdf_url)`).
   - *Hit:* Return JSON immediately (Latency: < 0.1s).
   - *Miss:* Proceed to Step 3.
3. **OCR (Modal):**
   - **Attempt 1:** Run **Granite-Docling**. If result is high-confidence & >50 chars, Success.
   - **Attempt 2 (Fallback):** If Docling fails, hot-swap/trigger **DeepSeek-OCR**. Return Markdown.
4. **Extraction (Groq/Ollama):** Send Markdown to LLM with schema instructions.
   - *Prod:* Groq (Llama 3-70B).
   - *Dev:* Ollama (Ministral 3B).
5. **Output:** Validate JSON against Pydantic Schema. Return to user.

System Architecture Flowchart 

------

## 3. 🔌 API Specification (The Contract)

**Endpoint:** `POST /api/v1/extract`

## 3.1 Request Body

```
json{
  "document_url": "https://example.com/invoice_123.pdf",
  "webhook_url": "https://client-app.com/webhook", 
  "schema_type": "invoice" 
}
```

- `webhook_url` (Optional): If provided, API returns `202 Accepted` and pushes result later. If null, API waits (Synchronous).
- `schema_type`: Defines expected output (e.g., "invoice", "balance_sheet", "generic").

## 3.2 Success Response (200 OK)

```
json{
  "status": "success",
  "processing_time": 4.25,
  "ocr_engine_used": "granite-docling", 
  "data": {
    "invoice_number": "INV-2025-001",
    "total_amount": 1500.00,
    "line_items": [
      {"desc": "Consulting", "qty": 10, "price": 150}
    ]
  }
}
```

## 3.3 Error Response (4xx/5xx)

```
json{
  "status": "error",
  "code": "OCR_FAILURE",
  "message": "Both OCR engines failed to extract legible text. Image quality may be too low."
}
```

------

## 4. 💻 Standard Operating Procedure (SOP)

## 4.1 Development Mode (Local)

- **Prerequisites:** Docker, Ollama (`deepseek-ocr:3b`, `ministral-3:3b` pulled).
- **Env Var:** `DEV_MODE=true`
- **Logic:**
  - **OCR:** Calls `localhost:11434` (Ollama) instead of Modal.
  - **LLM:** Calls `localhost:11434` (Ollama) instead of Groq.
- **Command:** `docker-compose up --build`

## 4.2 Production Mode (Cloud)

- **Prerequisites:** Modal Account (L4 GPU), Groq API Key, Redis URL.
- **Env Var:** `DEV_MODE=false`
- **Logic:**
  - **OCR:** Calls `ocr_service.process_pdf.remote(url)` (Modal).
  - **LLM:** Calls `GroqClient.chat.completions.create(...)`.
- **Deployment:** `modal deploy modal_app.py` -> `docker-compose up -d api_gateway`.

------

## 5. 🧱 Core Code Snippets (The "Brains")

## 5.1 The "Hybrid Switch" (Modal)

*File: `modal_app.py`*

```
python@app.cls(gpu="L4", timeout=120, keep_warm=1)
class OCRService:
    def process_pdf(self, url: str):
        # 1. Try Docling (Fast)
        try:
            res = self.docling.convert(url)
            md = res.document.export_to_markdown()
            if len(md) > 100: return {"engine": "docling", "markdown": md}
        except:
            pass 
        
        # 2. Fallback to DeepSeek (Robust)
        print("⚠️ Switching to DeepSeek-OCR...")
        # (DeepSeek Inference Code Here)
        return {"engine": "deepseek", "markdown": deepseek_md}
```

## 5.2 The "Safe LLM Caller" (Service Layer)

*File: `services/llm_service.py`*

```
pythondef extract_json(markdown_text, schema):
    client = get_client() # Returns Groq or Ollama based on ENV
    
    prompt = f"Extract {schema} from:\n{markdown_text}\nReturn JSON only."
    
    try:
        resp = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        # Fallback: Regex Repair
        import re
        match = re.search(r'\{.*\}', resp.choices[0].message.content, re.DOTALL)
        return json.loads(match.group()) if match else {}
```

------

## 6. 🛡️ Risk & Mitigation Strategies

| Risk                  | Mitigation                                    | Code Handler                                             |
| :-------------------- | :-------------------------------------------- | :------------------------------------------------------- |
| **OCR Hallucination** | DeepSeek might invent numbers on blank pages. | Check `len(markdown) < 20`. If true, return error early. |
| **Latency Spikes**    | Modal cold start takes 15s.                   | Set `keep_warm=1` in Modal decorator.                    |
| **JSON Parse Error**  | LLM outputs invalid JSON (trailing comma).    | Use `json_repair` library in `except` block.             |
| **Network Fail**      | Webhook fails to reach client.                | Implement `Retries=3` with Exponential Backoff (Celery). |

------

## 7. 🚀 Final Checklist (Pre-Flight)

-  **Local Test:** Run `dev_pipeline.py` with `DEV_MODE=true`. Pass/Fail?
-  **Secrets:** Are `GROQ_API_KEY` and `MODAL_TOKEN` set in `.env`?
-  **GPU Check:** Is Modal configured for `gpu="L4"` (or `A10G`)?
-  **Fallback Test:** Manually force Docling to fail (throw exception) and verify DeepSeek picks it up.
-  **Money Check:** Is `keep_warm=1` acceptable budget-wise (~$150/mo)? If not, use `container_idle_timeout=300`.

**This is your complete blueprint.** You have the architecture, the code logic, the fallback strategy, and the safety checks. You are ready to build. 🔨
