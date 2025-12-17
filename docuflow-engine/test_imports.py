import sys
from pathlib import Path

def test_basic_imports():
    """Test basic Python imports to check operability"""
    try:
        # Test core dependencies
        import fastapi
        print("✓ FastAPI import successful")
        
        import pydantic
        print("✓ Pydantic import successful")
        
        import requests
        print("✓ Requests import successful")
        
        # Test docling
        from docling.document_converter import DocumentConverter
        print("✓ Docling import successful")
        
        # Test pydantic-ai
        from pydantic_ai import Agent
        print("✓ Pydantic-AI import successful")
        
        # Test compression libraries
        import pikepdf
        print("✓ PikePDF import successful")
        
        from PIL import Image
        print("✓ Pillow import successful")
        
        import img2pdf
        print("✓ Img2pdf import successful")
        
        print("\nAll basic imports successful! Python environment seems operable.")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_basic_imports()