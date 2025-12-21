#!/usr/bin/env python3
"""
Test core functionality of DocuFlow engine:
- PDF generation and parsing with Docling
- LLM extraction with Ollama (Mistral)
"""

import asyncio
import tempfile
import os
from pathlib import Path
from fpdf import FPDF
from docling.document_converter import DocumentConverter
from pydantic_ai import Agent
from pydantic import BaseModel
import sys


class InvoiceData(BaseModel):
    vendor_name: str
    invoice_date: str
    total_amount: float
    currency: str
    invoice_number: str


async def test_docling_pdf():
    """Create a simple PDF and parse it with Docling."""
    print("Creating test PDF...")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="INVOICE", ln=1, align="C")
    pdf.cell(200, 10, txt="Vendor: Acme Corp", ln=1)
    pdf.cell(200, 10, txt="Invoice #: INV-2023-001", ln=1)
    pdf.cell(200, 10, txt="Date: 2023-12-15", ln=1)
    pdf.cell(200, 10, txt="Total: $123.45 USD", ln=1)
    pdf.cell(200, 10, txt="Thank you for your business!", ln=1)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        pdf_path = f.name
        pdf.output(pdf_path)
        print(f"PDF saved to {pdf_path}")

    try:
        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        markdown = result.document.export_to_markdown()
        print(f"Parsed markdown (first 200 chars): {markdown[:200]}...")
        assert "INVOICE" in markdown
        assert "Acme Corp" in markdown
        print("✅ Docling PDF parsing successful")
        return markdown
    finally:
        os.unlink(pdf_path)


async def test_llm_extraction(markdown: str):
    """Test LLM extraction with Ollama."""
    print("Testing LLM extraction...")
    import os

    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434/v1"
    agent = Agent(
        "ollama:ministral-3:3b",
        output_type=InvoiceData,
        system_prompt=(
            "You are an expert data extraction assistant. "
            "Analyze the provided markdown text from an invoice and extract structured data. "
            "Format dates as YYYY-MM-DD. If currency is missing, infer from context (usually USD or EUR)."
        ),
    )

    result = await agent.run(f"Extract invoice data from this content:\n\n{markdown}")
    extracted = result.output
    print(f"Extracted data: {extracted}")

    # Validate extracted fields
    assert extracted.vendor_name == "Acme Corp"
    assert extracted.invoice_date == "2023-12-15"
    assert extracted.total_amount == 123.45
    assert extracted.currency == "USD"
    assert extracted.invoice_number == "INV-2023-001"
    print("✅ LLM extraction successful")
    return extracted


async def main():
    print("=== DocuFlow Engine Core Test ===")
    try:
        markdown = await test_docling_pdf()
        extracted = await test_llm_extraction(markdown)
        print("\n✅ All tests passed!")
        return 0
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
