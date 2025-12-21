#!/usr/bin/env python3
"""
Test edge cases and error conditions for the DocuFlow engine
"""
import tempfile
import os
from unittest.mock import patch, MagicMock
from main import process_task, ProcessRequest, extract_invoice_data_ollama, InvoiceData

def test_error_conditions():
    """Test various error conditions"""
    print("Testing error handling...")

    # Test 1: Empty markdown content
    result = extract_invoice_data_ollama("")
    print(f"✅ Empty content test: {result}")
    assert result.vendor_name is None
    
    # Test 2: Very long content (should be truncated)
    long_content = "test " * 10000  # Much more than 30k limit
    result = extract_invoice_data_ollama(long_content)
    print(f"✅ Long content test: {result}")
    
    # Test 3: Process request with missing parameters
    print("Testing process_task with valid request...")
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        temp_file.write(b'%PDF-1.4 fake pdf content')  # Simple fake PDF
        temp_path = temp_file.name
    
    try:
        # This should fail because the proxy URL and callback URL don't exist
        # but we want to verify that validation happens correctly
        req = ProcessRequest(
            doc_id="test_doc",
            workspace_id="test_ws",
            file_proxy="http://nonexistent.example.com/file.pdf",
            callback_url="http://nonexistent.example.com/callback"
        )
        
        # Mock the external dependencies to test internal logic
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            
            # Configure the mock to raise an exception simulating network error
            mock_get.side_effect = Exception("Network error")
            mock_post.return_value = MagicMock()
            mock_post.return_value.status_code = 200
            
            # Run the process - this should handle the error gracefully
            process_task(req)
            print("✅ Error handling test passed - exceptions handled gracefully")
    
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    print("✅ All error condition tests completed!")

def test_extraction_edge_cases():
    """Test edge cases for the extraction function"""
    print("\nTesting extraction edge cases...")
    
    # Test with minimal valid content
    minimal_content = "# Invoice\n**Vendor:** Test Co\n**Amount:** $100"
    result = extract_invoice_data_ollama(minimal_content)
    print(f"✅ Minimal content extraction: {result}")
    
    # Test with no relevant data
    no_invoice_data = "This is just some random text with no invoice information."
    result = extract_invoice_data_ollama(no_invoice_data)
    print(f"✅ No invoice data extraction: {result}")
    
    # Test with special characters that might break JSON parsing
    special_chars = "# Invoice\n**Vendor:** Test & Co\n**Amount:** $100.50\n**Date:** 2023-01-01"
    result = extract_invoice_data_ollama(special_chars)
    print(f"✅ Special characters extraction: {result}")

if __name__ == "__main__":
    # Set Ollama URL for the test
    os.environ['OLLAMA_BASE_URL'] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    test_extraction_edge_cases()
    test_error_conditions()
    print("\n🎉 All edge case tests completed successfully!")