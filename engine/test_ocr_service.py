"""
Comprehensive test suite for OCR Service following TDD principles
Tests all functionality including error handling, timeouts, and validation
"""
import os
import sys
import tempfile
import json
import base64
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import Timeout, ConnectionError, RequestException

# Add the current directory to Python path
sys.path.append('.')

from services.ocr_service import (
    OllamaOCRClient, OCRError, FileValidationError,
    get_ocr_client, test_ocr_file_validation, test_base64_encoding
)


class TestOCRFileValidation:
    """Test file validation functionality"""
    
    def test_valid_pdf_file(self):
        """Test validation of a valid PDF file"""
        client = OllamaOCRClient()
        
        # Create a valid PDF file (dummy content for testing)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 dummy pdf content")
            temp_path = f.name
        
        try:
            result = client.validate_file(temp_path)
            assert result is True
        finally:
            os.unlink(temp_path)
    
    def test_nonexistent_file(self):
        """Test validation of non-existent file"""
        client = OllamaOCRClient()
        
        with pytest.raises(FileValidationError) as exc_info:
            client.validate_file("nonexistent.pdf")
        
        assert "File not found" in str(exc_info.value)
    
    def test_oversized_file(self):
        """Test validation of oversized file"""
        client = OllamaOCRClient()
        
        # Create a large file (simulate oversized)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"x" * (11 * 1024 * 1024))  # 11MB
            temp_path = f.name
        
        try:
            with pytest.raises(FileValidationError) as exc_info:
                client.validate_file(temp_path)
            assert "File too large" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_invalid_file_type(self):
        """Test validation of invalid file type"""
        client = OllamaOCRClient()
        
        # Create an invalid file type
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"dummy exe content")
            temp_path = f.name
        
        try:
            with pytest.raises(FileValidationError) as exc_info:
                client.validate_file(temp_path)
            assert "File type not allowed" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
    
    def test_small_image_resolution(self):
        """Test validation of image with insufficient resolution"""
        client = OllamaOCRClient()
        
        # Create a small image (simulate low resolution)
        try:
            from PIL import Image
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                # Create a 500x500 image (below 1000px minimum)
                img = Image.new('RGB', (500, 500), color='white')
                img.save(f.name)
                temp_path = f.name
            
            try:
                with pytest.raises(FileValidationError) as exc_info:
                    client.validate_file(temp_path)
                assert "Image width too small" in str(exc_info.value)
            finally:
                os.unlink(temp_path)
        except ImportError:
            pytest.skip("PIL not available for image testing")


class TestBase64Encoding:
    """Test base64 encoding functionality"""
    
    def test_valid_file_encoding(self):
        """Test encoding of valid file"""
        client = OllamaOCRClient()
        
        # Create a test file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content for base64 encoding")
            temp_path = f.name
        
        try:
            encoded = client.encode_file_to_base64(temp_path)
            assert len(encoded) > 30  # Adjusted for test content
            assert isinstance(encoded, str)
            
            # Verify it's valid base64
            decoded = base64.b64decode(encoded)
            assert decoded == b"test content for base64 encoding"
        finally:
            os.unlink(temp_path)
    
    def test_small_file_encoding(self):
        """Test encoding of file that's too small"""
        client = OllamaOCRClient()
        
        # Create a very small file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"x")  # Very small content
            temp_path = f.name
        
        try:
            with pytest.raises(FileValidationError) as exc_info:
                client.encode_file_to_base64(temp_path)
            assert "File data too small/corrupt" in str(exc_info.value)
        finally:
            os.unlink(temp_path)


class TestOllamaOCRCalls:
    """Test Ollama OCR API calls with mocked responses"""
    
    @patch('requests.post')
    def test_successful_ocr_call(self, mock_post):
        """Test successful OCR API call"""
        client = OllamaOCRClient()
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "OCR text result"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = client.call_ollama_ocr(
            "deepseek-ocr:3b", 
            "base64_image_data", 
            "Convert to markdown"
        )
        
        assert result["response"] == "OCR text result"
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_model_not_found_404(self, mock_post):
        """Test 404 model not found error"""
        client = OllamaOCRClient()
        
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response
        
        with pytest.raises(OCRError) as exc_info:
            client.call_ollama_ocr("deepseek-ocr:3b", "base64_image_data", "Convert to markdown")
        
        assert "not found" in str(exc_info.value)
        assert "ollama pull" in str(exc_info.value)
    
    @patch('requests.post')
    def test_timeout_with_retry(self, mock_post):
        """Test timeout handling with retry"""
        client = OllamaOCRClient()
        
        # First call times out, second succeeds
        mock_post.side_effect = [Timeout("Connection timed out"), Mock(
            status_code=200,
            json=lambda: {"response": "OCR result"},
            raise_for_status=lambda: None
        )]
        
        result = client.call_ollama_ocr("deepseek-ocr:3b", "base64_image_data", "Convert to markdown")
        
        assert result["response"] == "OCR result"
        assert mock_post.call_count == 2
    
    @patch('requests.post')
    def test_connection_error(self, mock_post):
        """Test connection error handling"""
        client = OllamaOCRClient()
        
        # Mock connection error
        mock_post.side_effect = ConnectionError("Connection refused")
        
        with pytest.raises(OCRError) as exc_info:
            client.call_ollama_ocr("deepseek-ocr:3b", "base64_image_data", "Convert to markdown")
        
        assert "Could not connect to Ollama" in str(exc_info.value)


class TestGraniteDoclingProcessing:
    """Test Granite-Docling processing functionality"""
    
    @patch('services.ocr_service.DocumentConverter')
    def test_successful_granite_processing(self, mock_converter_class):
        """Test successful Granite-Docling processing"""
        client = OllamaOCRClient()
        
        # Mock DocumentConverter
        mock_converter = Mock()
        mock_doc_result = Mock()
        mock_document = Mock()
        mock_document.export_to_markdown.return_value = "Markdown content from document with sufficient length to pass the 100 character threshold for testing purposes"
        mock_doc_result.document = mock_document
        mock_converter.convert.return_value = mock_doc_result
        mock_converter_class.return_value = mock_converter
        
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test content")
            temp_path = f.name
        
        try:
            markdown, engine = client.process_with_granite_docling(temp_path)
            assert "Markdown content from document" in markdown
            assert len(markdown) > 100  # Ensure it's long enough
            assert engine == "granite-docling"
        finally:
            os.unlink(temp_path)
    
    @patch('services.ocr_service.DocumentConverter')
    def test_insufficient_content_granite(self, mock_converter_class):
        """Test Granite-Docling with insufficient content"""
        client = OllamaOCRClient()
        
        # Mock DocumentConverter with short content
        mock_converter = Mock()
        mock_doc_result = Mock()
        mock_document = Mock()
        mock_document.export_to_markdown.return_value = "Short"  # Less than 100 chars
        mock_doc_result.document = mock_document
        mock_converter.convert.return_value = mock_doc_result
        mock_converter_class.return_value = mock_converter
        
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test content")
            temp_path = f.name
        
        try:
            with pytest.raises(OCRError) as exc_info:
                client.process_with_granite_docling(temp_path)
            assert "insufficient content" in str(exc_info.value)
        finally:
            os.unlink(temp_path)


class TestDeepSeekOCRProcessing:
    """Test DeepSeek-OCR processing functionality"""
    
    @patch('services.ocr_service.OllamaOCRClient.call_ollama_ocr')
    def test_successful_deepseek_processing(self, mock_ocr_call):
        """Test successful DeepSeek-OCR processing"""
        client = OllamaOCRClient()
        
        # Mock successful OCR response
        mock_ocr_call.return_value = {"response": "DeepSeek OCR result with good content length"}
        
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Create a larger fake image content that will produce sufficient base64
            f.write(b"fake image content that is much longer to ensure the base64 encoding produces more than 30 characters which is required for the validation to pass in our test environment")
            temp_path = f.name
        
        try:
            markdown, engine = client.process_with_deepseek_ocr(temp_path)
            assert "DeepSeek OCR result" in markdown
            assert engine == "deepseek-ocr"
        finally:
            os.unlink(temp_path)
    
    @patch('services.ocr_service.OllamaOCRClient.call_ollama_ocr')
    def test_deepseek_hallucination_detection(self, mock_ocr_call):
        """Test DeepSeek-OCR hallucination detection"""
        client = OllamaOCRClient()
        
        # Mock response with very short content (hallucination indicator)
        mock_ocr_call.return_value = {"response": "   "}  # Very short/empty
        
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Create a larger fake image content that will produce sufficient base64
            f.write(b"fake image content that is much longer to ensure the base64 encoding produces more than 30 characters which is required for the validation to pass in our test environment")
            temp_path = f.name
        
        try:
            with pytest.raises(OCRError) as exc_info:
                client.process_with_deepseek_ocr(temp_path)
            assert "insufficient content" in str(exc_info.value)
            assert "hallucination" in str(exc_info.value).lower()
        finally:
            os.unlink(temp_path)
    
    @patch('services.ocr_service.OllamaOCRClient.call_ollama_ocr')
    def test_deepseek_garbage_detection(self, mock_ocr_call):
        """Test DeepSeek-OCR garbage character detection"""
        client = OllamaOCRClient()
        
        # Mock response with garbage characters
        mock_ocr_call.return_value = {"response": "Some text &&&^^^%%% more text"}
        
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Create a larger fake image content that will produce sufficient base64
            f.write(b"fake image content that is much longer to ensure the base64 encoding produces more than 30 characters which is required for the validation to pass in our test environment")
            temp_path = f.name
        
        try:
            with pytest.raises(OCRError) as exc_info:
                client.process_with_deepseek_ocr(temp_path)
            assert "garbage characters" in str(exc_info.value)
        finally:
            os.unlink(temp_path)


class TestHybridOCRProcessing:
    """Test hybrid OCR processing with fallback logic"""
    
    @patch('services.ocr_service.OllamaOCRClient.process_with_granite_docling')
    @patch('services.ocr_service.OllamaOCRClient.process_with_deepseek_ocr')
    def test_successful_granite_path(self, mock_deepseek, mock_granite):
        """Test successful processing via Granite-Docling path"""
        client = OllamaOCRClient()
        
        # Mock successful Granite processing
        mock_granite.return_value = ("Granite markdown content", "granite-docling")
        
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test content")
            temp_path = f.name
        
        try:
            result = client.hybrid_ocr_process(temp_path)
            
            assert result["status"] == "success"
            assert result["markdown"] == "Granite markdown content"
            assert result["engine_used"] == "granite-docling"
            assert "processing_time" in result
            assert result["confidence"] in ["high", "medium"]
            
            # DeepSeek should not be called
            mock_deepseek.assert_not_called()
            
        finally:
            os.unlink(temp_path)
    
    @patch('services.ocr_service.OllamaOCRClient.process_with_granite_docling')
    @patch('services.ocr_service.OllamaOCRClient.process_with_deepseek_ocr')
    def test_granite_failure_deepseek_fallback(self, mock_deepseek, mock_granite):
        """Test Granite failure with DeepSeek fallback"""
        client = OllamaOCRClient()
        
        # Mock Granite failure
        mock_granite.side_effect = OCRError("Granite failed")
        
        # Mock successful DeepSeek processing
        mock_deepseek.return_value = ("DeepSeek markdown content", "deepseek-ocr")
        
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test content")
            temp_path = f.name
        
        try:
            result = client.hybrid_ocr_process(temp_path)
            
            assert result["status"] == "success"
            assert result["markdown"] == "DeepSeek markdown content"
            assert result["engine_used"] == "deepseek-ocr"
            
            # Both should be called
            mock_granite.assert_called_once()
            mock_deepseek.assert_called_once()
            
        finally:
            os.unlink(temp_path)
    
    @patch('services.ocr_service.OllamaOCRClient.process_with_granite_docling')
    @patch('services.ocr_service.OllamaOCRClient.process_with_deepseek_ocr')
    def test_both_engines_fail(self, mock_deepseek, mock_granite):
        """Test complete failure when both engines fail"""
        client = OllamaOCRClient()
        
        # Mock both engines failing
        mock_granite.side_effect = OCRError("Granite failed")
        mock_deepseek.side_effect = OCRError("DeepSeek failed")
        
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test content")
            temp_path = f.name
        
        try:
            result = client.hybrid_ocr_process(temp_path)
            
            assert result["status"] == "error"
            assert "error" in result
            assert result["engine_used"] == "none"
            assert "processing_time" in result
            
        finally:
            os.unlink(temp_path)


class TestClientFactory:
    """Test OCR client factory function"""
    
    @patch.dict(os.environ, {"DEV_MODE": "true"})
    def test_dev_mode_client(self):
        """Test client creation in dev mode"""
        client = get_ocr_client()
        assert isinstance(client, OllamaOCRClient)
    
    @patch.dict(os.environ, {"DEV_MODE": "false"})
    def test_prod_mode_client(self):
        """Test client creation in prod mode"""
        client = get_ocr_client()
        assert isinstance(client, OllamaOCRClient)
        # In real implementation, this would be a Modal client


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_file_content(self):
        """Test handling of empty file content"""
        client = OllamaOCRClient()
        
        # Create empty file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"")  # Empty content
            temp_path = f.name
        
        try:
            with pytest.raises(FileValidationError):
                client.validate_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_corrupted_pdf_file(self):
        """Test handling of corrupted PDF file"""
        client = OllamaOCRClient()
        
        # Create corrupted PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"not a valid pdf")
            temp_path = f.name
        
        try:
            # This should fail during Docling processing
            with pytest.raises(OCRError):
                client.process_with_granite_docling(temp_path)
        finally:
            os.unlink(temp_path)


def run_comprehensive_tests():
    """Run all comprehensive tests"""
    print("🧪 Running Comprehensive OCR Service Tests...")
    
    # Import and run pytest programmatically
    import subprocess
    
    # Run tests with verbose output
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        __file__, 
        "-v", 
        "--tb=short"
    ], capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    if result.returncode == 0:
        print("🎉 All comprehensive tests passed!")
        return True
    else:
        print(f"❌ Some tests failed with return code: {result.returncode}")
        return False


if __name__ == "__main__":
    success = run_comprehensive_tests()
    if not success:
        sys.exit(1)