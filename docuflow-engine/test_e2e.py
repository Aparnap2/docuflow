#!/usr/bin/env python3
"""
End-to-end test for the DocuFlow engine
Tests the complete workflow: PDF -> Docling -> Ollama -> Structured Data
"""
import os
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from docling.document_converter import DocumentConverter
from main import extract_invoice_data_ollama, ProcessRequest, InvoiceData

def create_test_pdf():
    """Create a more realistic test invoice PDF"""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        c = canvas.Canvas(temp_pdf.name, pagesize=letter)
        
        # Add invoice content
        y = 750
        c.drawString(100, y, "INVOICE")
        y -= 30
        c.drawString(100, y, "ACME Corporation")
        y -= 20
        c.drawString(100, y, "123 Business Ave, Suite 100")
        y -= 20
        c.drawString(100, y, "New York, NY 10001")
        y -= 40
        c.drawString(100, y, "Invoice Number: INV-2023-001")
        y -= 20
        c.drawString(100, y, "Invoice Date: 2023-06-15")
        y -= 20
        c.drawString(100, y, "Due Date: 2023-07-15")
        y -= 40
        c.drawString(100, y, "Bill To:")
        y -= 20
        c.drawString(100, y, "XYZ Client")
        y -= 20
        c.drawString(100, y, "456 Client Street")
        y -= 20
        c.drawString(100, y, "Boston, MA 02101")
        y -= 40
        c.drawString(100, y, "Description              Quantity    Rate      Amount")
        y -= 20
        c.drawString(100, y, "Professional Services    10          $50.00    $500.00")
        y -= 20
        c.drawString(100, y, "Additional Expenses      1           $75.00    $75.00")
        y -= 40
        c.drawString(100, y, "Subtotal:                          $575.00")
        y -= 20
        c.drawString(100, y, "Tax (8.5%):                        $48.88")
        y -= 20
        c.drawString(100, y, "Total:                             $623.88")
        
        c.save()
        return temp_pdf.name

def test_end_to_end():
    """Test the complete document processing pipeline"""
    print("Starting end-to-end test...")
    
    # 1. Create test PDF
    pdf_path = create_test_pdf()
    print(f"✅ Created test PDF: {os.path.basename(pdf_path)}")
    
    # 2. Convert PDF to markdown using Docling
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    markdown = result.document.export_to_markdown()
    print("✅ Converted PDF to markdown")
    
    # 3. Extract data using Ollama
    extracted_data = extract_invoice_data_ollama(markdown)
    print(f"✅ Extracted data using Ollama: {extracted_data}")
    
    # 4. Validate extracted data
    expected_fields = ['vendor_name', 'total_amount', 'invoice_date', 'invoice_number', 'currency']
    for field in expected_fields:
        value = getattr(extracted_data, field)
        print(f"  - {field}: {value}")
    
    # Basic validations
    assert extracted_data.vendor_name is not None, "Vendor name should be extracted"
    assert extracted_data.total_amount is not None, "Total amount should be extracted" 
    assert extracted_data.invoice_date is not None, "Invoice date should be extracted"
    assert extracted_data.invoice_number is not None, "Invoice number should be extracted"
    
    print("✅ All validations passed!")
    
    # 5. Clean up
    os.unlink(pdf_path)
    print("✅ Test completed successfully!")
    
    return extracted_data

if __name__ == "__main__":
    # Set Ollama URL for the test
    os.environ['OLLAMA_BASE_URL'] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    result = test_end_to_end()
    print(f"\nFinal result: {result}")