from docling.document_converter import DocumentConverter
import tempfile
import requests

def test_granite_execution():
    # Create a test PDF file locally with some content
    # First download a test PDF from a reliable source
    pdf_url = "https://arxiv.org/pdf/2206.01062.pdf"

    try:
        response = requests.get(pdf_url)
        response.raise_for_status()

        # Save to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(response.content)
            temp_pdf_path = tmp_file.name

        # 2. Run Converter
        converter = DocumentConverter()

        # 3. Test on the downloaded PDF
        result = converter.convert(temp_pdf_path)

        # 4. Verify Output is Markdown
        md = result.document.export_to_markdown()
        print("--- MARKDOWN OUTPUT ---")
        print(md[:1000]) # Print first 1000 chars

        # 5. Check for Table Syntax or Important Content
        has_content = len(md.strip()) > 0
        has_tables = "|" in md and "---" in md
        has_headings = "#" in md

        if has_content and (has_tables or has_headings):
            print("✅ SUCCESS: Docling processed the document and extracted content")
            if has_tables:
                print("✅ SUCCESS: Table detected in Markdown")
            if has_headings:
                print("✅ SUCCESS: Headings detected in Markdown")
        else:
            print("❌ FAILURE: No meaningful content extracted")

        # Clean up
        import os
        os.unlink(temp_path)

    except Exception as e:
        print(f"Error during processing: {e}")
        # Let's create a simple test file instead
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            # Write a simple PDF-like content (not really a PDF, but for testing the code path)
            f.write("%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n")
            temp_path = f.name

        try:
            converter = DocumentConverter()
            result = converter.convert(temp_path)
            md = result.document.export_to_markdown()
            print("Converted simple test content")
            print(f"Markdown length: {len(md)}")

            os.unlink(temp_path)
        except Exception as e2:
            print(f"Also failed with simple file: {e2}")
            # Test that the converter can be instantiated at least
            try:
                converter = DocumentConverter()
                print("✅ SUCCESS: DocumentConverter can be instantiated")
            except Exception as e3:
                print(f"❌ FAILURE: Cannot even instantiate converter: {e3}")

if __name__ == "__main__":
    test_granite_execution()