import os
import json
import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field
from docling.document_converter import DocumentConverter
from openai import OpenAI  # Using OpenAI compatible interface for Ollama
from apify import Actor

# --- Data Models (for Llama Structured Output) ---
class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total: float

class InvoiceData(BaseModel):
    vendor_name: str
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    total_amount: float
    line_items: List[LineItem]
    currency: str = Field(default="USD", description="ISO 4217 currency code (e.g. USD, EUR)")

async def main():
    await Actor.init()

    # Get input
    actor_input = await Actor.get_input() or {}
    pdf_url = actor_input.get('pdf_url')
    # Use Ollama-compatible variables instead of Groq
    ollama_base_url = actor_input.get('ollama_base_url') or os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
    llm_model = actor_input.get('llm_model') or os.getenv('LLM_MODEL', 'ministral-3:3b')  # Updated to use Ollama model
    email = actor_input.get('email')  # For lead capture

    if not pdf_url:
        print("❌ Missing inputs")
        await Actor.fail(status_message="Missing 'pdf_url' in input")  # FIXED: Use keyword argument
        await Actor.exit()
        return

    print(f"🚀 Processing: {pdf_url}")
    if email:
        print(f"📧 Lead captured: {email}")

    try:
        # 1. Docling: PDF -> Markdown
        print("📄 Converting PDF to Markdown...")
        converter = DocumentConverter()
        result = converter.convert(pdf_url)
        markdown_text = result.document.export_to_markdown()

        # 2. Ollama LLM: Markdown -> JSON (using Ollama with ministral-3:3b)
        print("🧠 Reasoning with Ollama LLM...")
        # Initialize Ollama client using OpenAI-compatible interface
        client = OpenAI(
            base_url=ollama_base_url,  # Updated to use Ollama base URL
            api_key="ollama"  # Ollama doesn't require a real API key
        )

        # Create a structured extraction prompt
        extraction_prompt = f"""
        You are an expert invoice parser. Extract the following fields from the invoice content:

        - vendor_name: The name of the vendor/supplier
        - invoice_number: The invoice identifier (if present)
        - date: The invoice date (in YYYY-MM-DD format, if present)
        - total_amount: The total amount charged
        - line_items: List of line items with description, quantity, unit_price, and total
        - currency: The currency code (e.g. USD, EUR)

        Invoice content:
        {markdown_text[:15000]}  # Truncate if massive

        Respond ONLY with valid JSON that matches this structure:
        {{
            "vendor_name": "...",
            "invoice_number": "...",
            "date": "...",
            "total_amount": ...,
            "line_items": [
                {{
                    "description": "...",
                    "quantity": ...,
                    "unit_price": ...,
                    "total": ...
                }}
            ],
            "currency": "..."
        }}
        """

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert invoice parser. Respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": extraction_prompt
                }
            ],
            model=llm_model,  # Updated to use Ollama model name
            response_format={"type": "json_object"},
            temperature=0.1
        )

        extracted_json_str = chat_completion.choices[0].message.content
        final_data = json.loads(extracted_json_str)

        # 3. Output the results
        print("✅ Success! Pushing data...")
        await Actor.push_data(final_data)

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        # FIXED: Use keyword argument for Actor.fail
        await Actor.fail(status_message=f"Processing failed: {str(e)}")

    await Actor.exit()

if __name__ == '__main__':
    # Run the async main function
    asyncio.run(main())