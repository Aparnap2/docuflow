"""
Main application file for the Agentic OCR Service
Updated to use the new hybrid OCR architecture
"""
import os
import sys
import logging
from fastapi import FastAPI
from main_new import app as new_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Re-export the new application
app = new_app

if __name__ == "__main__":
    import uvicorn
    
    # Run the TDD tests first
    print("🧪 Running OCR Service TDD Tests...")
    try:
        # Import and run OCR service tests
        from services.ocr_service import test_ocr_file_validation, test_base64_encoding
        test_ocr_file_validation()
        test_base64_encoding()
        
        # Import and run integration tests
        import subprocess
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "test_ocr_service.py", "test_integration.py", 
            "-v", "--tb=short"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ All TDD tests passed!")
            print("🚀 Starting Agentic OCR Service...")
            uvicorn.run(app, host="0.0.0.0", port=8000)
        else:
            print(f"❌ Tests failed:")
            print(result.stdout)
            print(result.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        sys.exit(1)