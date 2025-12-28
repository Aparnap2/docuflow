"""
Local test for Sarah AI Apify Actor
This script tests the actor functionality locally before deployment
"""

import os
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock

# Add the current directory to the path so we can import from src
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_dependencies():
    """Test that all required dependencies can be imported"""
    print("Testing dependencies...")
    
    try:
        import apify
        print("✅ apify imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import apify: {e}")
        return False
    
    try:
        import docling
        print("✅ docling imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import docling: {e}")
        return False
    
    try:
        from groq import Groq
        print("✅ groq imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import groq: {e}")
        return False
    
    try:
        from pydantic import BaseModel
        print("✅ pydantic imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import pydantic: {e}")
        return False
    
    return True

def test_main_logic():
    """Test the main processing logic without external dependencies"""
    print("\nTesting main processing logic...")
    
    # Import the main module
    try:
        from src.main import main, InvoiceData, LineItem
        print("✅ Successfully imported main module and data models")
    except Exception as e:
        print(f"❌ Failed to import main module: {e}")
        return False
    
    # Test data models
    try:
        # Test LineItem model
        line_item = LineItem(
            description="Test Item",
            quantity=2.0,
            unit_price=10.50,
            total=21.00
        )
        assert line_item.description == "Test Item"
        assert line_item.quantity == 2.0
        print("✅ LineItem model works correctly")
        
        # Test InvoiceData model
        invoice_data = InvoiceData(
            vendor_name="Test Vendor",
            invoice_number="INV-12345",
            date="2025-12-26",
            total_amount=105.50,
            line_items=[line_item],
            currency="USD"
        )
        assert invoice_data.vendor_name == "Test Vendor"
        assert len(invoice_data.line_items) == 1
        print("✅ InvoiceData model works correctly")
        
    except Exception as e:
        print(f"❌ Failed to test data models: {e}")
        return False
    
    return True

def test_local_simulation():
    """Simulate the processing workflow locally"""
    print("\nTesting local simulation...")
    
    # Create storage directory structure
    os.makedirs("./storage/key_value_stores/default", exist_ok=True)
    os.makedirs("./storage/datasets/default", exist_ok=True)
    
    # Create mock input
    mock_input = {
        "pdf_url": "https://github.com/docling-project/docling/raw/main/tests/data/2206.01062.pdf",
        "groq_api_key": "gsk_mock_key_for_testing"  # This would be a real key in production
    }
    
    # Write mock input to storage
    with open("./storage/key_value_stores/default/INPUT.json", "w") as f:
        json.dump(mock_input, f)
    
    print("✅ Created mock input file")
    
    # Verify the file exists
    if os.path.exists("./storage/key_value_stores/default/INPUT.json"):
        print("✅ Mock input file exists at correct location")
    else:
        print("❌ Mock input file not found")
        return False
    
    # Test that main.py exists and has the expected content
    if os.path.exists("./src/main.py"):
        with open("./src/main.py", "r") as f:
            content = f.read()
        
        if "async def main" in content:
            print("✅ main.py has async main function")
        else:
            print("❌ main.py missing async main function")
            return False
            
        if "Actor.get_input()" in content:
            print("✅ main.py uses Actor.get_input()")
        else:
            print("❌ main.py missing Actor.get_input() call")
            return False
            
        if "Actor.push_data(" in content:
            print("✅ main.py uses Actor.push_data()")
        else:
            print("❌ main.py missing Actor.push_data() call")
            return False
    
    print("✅ Local simulation setup complete")
    return True

def run_local_tests():
    """Run all local tests"""
    print("=== Sarah AI Local Testing ===\n")
    
    success = True
    
    # Test 1: Dependencies
    success &= test_dependencies()
    
    # Test 2: Main logic
    success &= test_main_logic()
    
    # Test 3: Local simulation
    success &= test_local_simulation()
    
    if success:
        print("\n🎉 All local tests passed!")
        print("✅ Ready to test with Docker or deploy to Apify!")
        print("\nTo run with real dependencies:")
        print("1. Add your real GROQ API key to the input")
        print("2. Run with: python -m src.main")
        print("3. Or build and run with Docker")
        return True
    else:
        print("\n❌ Some local tests failed!")
        return False

if __name__ == "__main__":
    success = run_local_tests()
    if not success:
        exit(1)