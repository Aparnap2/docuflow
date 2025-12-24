#!/usr/bin/env python3
"""
Simple test script to validate engine functionality
"""
import sys
import os
sys.path.append('.')

def test_imports():
    """Test that all required modules can be imported"""
    try:
        import fastapi
        import uvicorn
        import docling
        import langextract
        import google.generativeai as genai
        import boto3
        import pydantic
        import requests
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality of key components"""
    try:
        # Test FastAPI app creation
        from fastapi import FastAPI
        app = FastAPI()
        print("✅ FastAPI app creation successful")
        
        # Test Pydantic model creation
        from pydantic import BaseModel
        class TestModel(BaseModel):
            name: str
            value: int
        test = TestModel(name="test", value=42)
        print("✅ Pydantic model creation successful")
        
        # Test Docling document creation
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        print("✅ Docling converter creation successful")
        
        return True
    except Exception as e:
        print(f"❌ Functionality test error: {e}")
        return False

def test_engine_main():
    """Test that main.py can be imported without errors"""
    try:
        # Check if main.py exists and can be imported
        if os.path.exists('main.py'):
            import main
            print("✅ main.py import successful")
            return True
        else:
            print("❌ main.py not found")
            return False
    except Exception as e:
        print(f"❌ main.py import error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting engine tests...")
    
    tests = [
        ("Import Test", test_imports),
        ("Basic Functionality Test", test_basic_functionality),
        ("Engine Main Test", test_engine_main),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Engine is ready for deployment.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please fix the issues before deployment.")
        sys.exit(1)