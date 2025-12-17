#!/usr/bin/env python3
"""
Basic Python operability test for Docuflow engine
"""
import sys
import importlib.util
from pathlib import Path

def test_python_operability():
    """Test basic Python operability for docuflow-engine"""
    print("Testing Python operability...")
    
    # Test imports that are critical for the application
    required_imports = [
        ("fastapi", "FastAPI"),
        ("pydantic", "BaseModel"),
        ("docling.document_converter", "DocumentConverter"),
        ("pydantic_ai", "Agent"),
        ("requests", "get"),
        ("pikepdf", "Pdf"),
        ("PIL.Image", "Image"),
        ("img2pdf", None),
        ("loguru", "logger"),
    ]
    
    missing_imports = []
    
    for imp_path, attr in required_imports:
        try:
            if attr:
                # Import specific attribute
                module = importlib.import_module(imp_path)
                getattr(module, attr)
            else:
                # Import module only
                importlib.import_module(imp_path)
            print(f"✓ {imp_path} import successful")
        except ImportError as e:
            print(f"✗ Failed to import {imp_path}: {e}")
            missing_imports.append(imp_path)
    
    # Test that main.py can be compiled without syntax errors
    try:
        main_py_path = Path(__file__).parent / "main.py"
        with open(main_py_path, 'r', encoding='utf-8') as f:
            code = f.read()
        compile(code, str(main_py_path), 'exec')
        print("✓ main.py syntax is valid")
    except SyntaxError as e:
        print(f"✗ main.py has syntax errors: {e}")
        missing_imports.append("main.py syntax")
    except Exception as e:
        print(f"✗ Error compiling main.py: {e}")
        missing_imports.append("main.py compilation")
    
    # Test gdrive utility
    try:
        import utils.gdrive
        print("✓ utils.gdrive import successful")
    except ImportError as e:
        print(f"✗ Failed to import utils.gdrive: {e}")
        missing_imports.append("utils.gdrive")
    
    if missing_imports:
        print(f"\n❌ {len(missing_imports)} critical imports failed")
        return False
    else:
        print(f"\n✅ All {len(required_imports)} critical imports successful")
        return True

if __name__ == "__main__":
    success = test_python_operability()
    sys.exit(0 if success else 1)