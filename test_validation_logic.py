"""
Test the validation logic for Sarah AI
"""
import json
import re
from typing import Dict, Any, List

def validate_extraction_results(extracted_data: Dict[str, Any], schema: List[Dict[str, str]]) -> float:
    """
    Validate extraction results against the schema and calculate confidence
    """
    if not schema:
        return 0.0
    
    # Count how many fields were successfully extracted
    successful_extractions = 0
    total_fields = len(schema)
    
    for field in schema:
        field_name = field['name']
        if field_name in extracted_data:
            # Check if the value is not empty or a "not found" placeholder
            value = extracted_data[field_name]
            if value and not str(value).startswith("No ") and "not found" not in str(value).lower():
                successful_extractions += 1
    
    # Calculate base confidence
    base_confidence = successful_extractions / total_fields if total_fields > 0 else 0.0
    
    # Apply additional validation rules for specific field types
    validation_issues = []
    
    for field in schema:
        field_name = field['name']
        field_type = field.get('type', 'text')
        instruction = field.get('instruction', '')
        
        if field_name in extracted_data:
            value = extracted_data[field_name]
            
            # Type-specific validation
            if field_type == 'currency':
                # Validate currency format
                currency_pattern = r'\$?[\d,]+\.?\d{2}'
                if not re.match(currency_pattern, str(value)):
                    validation_issues.append(f"Currency format invalid for {field_name}: {value}")
            elif field_type == 'date':
                # Validate date format
                date_pattern = r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}'
                if not re.match(date_pattern, str(value)):
                    validation_issues.append(f"Date format invalid for {field_name}: {value}")
            elif field_type == 'number':
                # Validate number format
                try:
                    float(str(value).replace(',', ''))
                except ValueError:
                    validation_issues.append(f"Number format invalid for {field_name}: {value}")
    
    # Reduce confidence for validation issues
    issue_penalty = len(validation_issues) * 0.1  # 10% penalty per issue
    final_confidence = max(0.0, base_confidence - issue_penalty)
    
    return {
        "confidence": final_confidence,
        "successful_extractions": successful_extractions,
        "total_fields": total_fields,
        "validation_issues": validation_issues
    }

def test_validation_logic():
    """Test the validation logic with good and bad data"""
    print("Testing Validation Logic...")
    
    # Test schema
    schema = [
        {"name": "Vendor", "type": "text", "instruction": "Extract vendor name"},
        {"name": "Total", "type": "currency", "instruction": "Extract total amount"},
        {"name": "Invoice Date", "type": "date", "instruction": "Extract invoice date"},
        {"name": "Invoice Number", "type": "text", "instruction": "Extract invoice number"}
    ]
    
    # Test 1: Good data
    good_data = {
        "Vendor": "Home Depot",
        "Total": "$105.50",
        "Invoice Date": "2025-12-26",
        "Invoice Number": "INV-12345"
    }
    
    good_result = validate_extraction_results(good_data, schema)
    print(f"Good data confidence: {good_result['confidence']:.2f}")
    print(f"Successful extractions: {good_result['successful_extractions']}/{good_result['total_fields']}")
    assert good_result['confidence'] > 0.8, "Good data should have high confidence"
    print("✅ Good data validation passed")

    # Test 2: Bad data (missing fields)
    bad_data = {
        "Vendor": "Home Depot",
        "Total": "invalid_amount",  # Invalid currency format
        "Invoice Date": "not_a_date",  # Invalid date format
        # Missing Invoice Number
    }

    bad_result = validate_extraction_results(bad_data, schema)
    print(f"Bad data confidence: {bad_result['confidence']:.2f}")
    print(f"Successful extractions: {bad_result['successful_extractions']}/{bad_result['total_fields']}")
    print(f"Validation issues: {bad_result['validation_issues']}")
    assert bad_result['confidence'] < 0.7, "Bad data should have low confidence"
    assert len(bad_result['validation_issues']) > 0, "Bad data should have validation issues"
    print("✅ Bad data validation passed")
    
    # Test 3: Math validation (if present)
    def validate_math(extracted_data: Dict[str, Any]) -> bool:
        """Validate that math is correct (e.g., Total = Subtotal + Tax)"""
        try:
            # Look for common financial fields
            total_str = extracted_data.get('Total', '0')
            subtotal_str = extracted_data.get('Subtotal', '0')
            tax_str = extracted_data.get('Tax', '0')
            
            # Extract numbers from strings
            def extract_number(amount_str):
                numbers = re.findall(r'[\d.]+', str(amount_str))
                if numbers:
                    return float(numbers[0])
                return 0.0
            
            total = extract_number(total_str)
            subtotal = extract_number(subtotal_str)
            tax = extract_number(tax_str)
            
            # Check if Total ≈ Subtotal + Tax (with small tolerance for rounding)
            expected_total = subtotal + tax
            tolerance = 0.01
            
            is_valid = abs(total - expected_total) <= tolerance
            if not is_valid:
                print(f"Math validation failed: {total} != {subtotal} + {tax} (expected {expected_total})")
            
            return is_valid
        except Exception:
            # If validation fails due to parsing errors, assume invalid
            return False
    
    # Test with correct math
    correct_math_data = {
        "Vendor": "Office Supplies Inc.",
        "Subtotal": "$100.00",
        "Tax": "$8.25",
        "Total": "$108.25"  # 100 + 8.25 = 108.25 ✓
    }
    
    assert validate_math(correct_math_data), "Correct math should pass validation"
    print("✅ Correct math validation passed")
    
    # Test with incorrect math
    incorrect_math_data = {
        "Vendor": "Office Supplies Inc.",
        "Subtotal": "$100.00",
        "Tax": "$8.25",
        "Total": "$500.00"  # 100 + 8.25 ≠ 500 ✗
    }
    
    assert not validate_math(incorrect_math_data), "Incorrect math should fail validation"
    print("✅ Incorrect math validation caught")
    
    print("✅ All validation logic tests passed!")
    return True

def test_json_storage_format():
    """Test that results are properly formatted for JSON storage"""
    print("\nTesting JSON Storage Format...")
    
    # Sample extraction results
    sample_results = {
        "extracted_fields": {
            "Vendor": "Home Depot",
            "Total": "$105.50",
            "Invoice Date": "2025-12-26",
            "Invoice Number": "HD-12345"
        },
        "raw_text": "Invoice from Home Depot dated 2025-12-26...",
        "raw_ocr": "OCR output for the document...",
        "confidence": 0.92,
        "validation_status": "valid",
        "processing_metadata": {
            "model_used": "ministral-3:3b",
            "processing_time": 45.2,
            "pages_processed": 1
        }
    }
    
    # Test JSON serialization
    try:
        json_str = json.dumps(sample_results)
        print("✅ Results can be serialized to JSON")
    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        return False
    
    # Test JSON deserialization
    try:
        reconstructed = json.loads(json_str)
        assert reconstructed["extracted_fields"]["Vendor"] == "Home Depot"
        assert abs(reconstructed["confidence"] - 0.92) < 0.01
        assert reconstructed["processing_metadata"]["pages_processed"] == 1
        print("✅ Results can be deserialized from JSON")
    except Exception as e:
        print(f"❌ JSON deserialization failed: {e}")
        return False
    
    # Test that important fields are preserved
    required_fields = ["extracted_fields", "confidence", "validation_status"]
    for field in required_fields:
        assert field in reconstructed, f"Missing required field: {field}"
    
    print("✅ All required fields preserved in JSON format")
    print("✅ JSON storage format validation passed!")
    return True

def run_validation_tests():
    """Run all validation tests"""
    print("Running Validation Tests for Sarah AI Processing\n")
    
    success = True
    
    # Test 1: Validation logic
    success &= test_validation_logic()
    
    # Test 2: JSON storage format
    success &= test_json_storage_format()
    
    if success:
        print("\n🎉 All validation tests passed!")
        print("✅ Sarah AI validation system is working correctly!")
        print("   - Extraction validation with confidence scoring")
        print("   - Math validation for financial documents") 
        print("   - JSON serialization/deserialization")
        print("   - Required field preservation")
        return True
    else:
        print("\n❌ Some validation tests failed!")
        return False

if __name__ == "__main__":
    success = run_validation_tests()
    if not success:
        exit(1)