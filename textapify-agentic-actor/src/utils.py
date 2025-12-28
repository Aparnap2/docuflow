from typing import Dict, Any, List
from .models import ExtractedData

def validate_math(extracted_data: Dict[str, Any]) -> List[str]:
    """
    Validates mathematical consistency in extracted data.
    Returns list of validation errors if any.
    """
    errors = []
    
    # Calculate sum of line items
    line_items = extracted_data.get('line_items', [])
    calculated_total = sum(item.get('total', 0) for item in line_items)
    
    # Get the total amount
    total_amount = extracted_data.get('total_amount', 0)
    
    # Check if calculated total matches extracted total (with small tolerance for rounding)
    tolerance = 0.05  # Allow for small rounding differences
    if abs(calculated_total - total_amount) > tolerance:
        errors.append(f"Math Mismatch: Sum of lines ({calculated_total}) != Total ({total_amount})")
    
    # Validate tax calculation if both tax and subtotal are present
    tax_amount = extracted_data.get('tax_amount', 0)
    if 'subtotal' in extracted_data:  # If subtotal is provided
        subtotal = extracted_data['subtotal']
        expected_total = subtotal + tax_amount
        if abs(expected_total - total_amount) > tolerance:
            errors.append(f"Tax Math Error: Subtotal ({subtotal}) + Tax ({tax_amount}) != Total ({total_amount})")
    
    # Check for required fields
    if not extracted_data.get('vendor_name'):
        errors.append("Missing required field: vendor_name")
    
    if extracted_data.get('total_amount', 0) == 0:
        errors.append("Missing or zero total_amount")
    
    return errors

def validate_null_checks(extracted_data: Dict[str, Any]) -> List[str]:
    """
    Validates that critical fields are not null/empty.
    Returns list of validation errors if any.
    """
    errors = []
    
    required_fields = ['vendor_name', 'total_amount']
    
    for field in required_fields:
        value = extracted_data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"Missing required field: {field}")
    
    return errors

def calculate_confidence(extracted_data: Dict[str, Any]) -> float:
    """
    Calculates confidence score based on extraction completeness.
    Returns a value between 0 and 1.
    """
    if not extracted_data:
        return 0.0

    # Define fields that contribute to confidence
    important_fields = [
        'vendor_name', 'total_amount', 'invoice_date',
        'invoice_number', 'tax_amount', 'line_items'
    ]

    # Count filled important fields
    filled_fields = 0
    total_fields = len(important_fields)

    for field in important_fields:
        value = extracted_data.get(field)
        if value is not None:
            if isinstance(value, (str, list)) and len(str(value)) > 0:
                filled_fields += 1
            elif isinstance(value, (int, float)) and value != 0:
                filled_fields += 1
            elif not isinstance(value, (str, list, int, float)):
                filled_fields += 1  # Non-empty objects

    # Calculate base confidence
    base_confidence = filled_fields / total_fields if total_fields > 0 else 0.0

    # Adjust based on validation errors
    math_errors = validate_math(extracted_data)
    null_errors = validate_null_checks(extracted_data)
    total_errors = len(math_errors) + len(null_errors)

    # Reduce confidence for each validation error
    error_penalty = min(0.3, total_errors * 0.1)  # Max 30% penalty for errors
    final_confidence = max(0.0, base_confidence - error_penalty)

    return final_confidence

def validate_math(extracted_data: Dict[str, Any]) -> List[str]:
    """
    Validates mathematical consistency in extracted data.
    Returns list of validation errors if any.
    """
    errors = []

    # Calculate sum of line items
    line_items = extracted_data.get('line_items', [])
    calculated_total = sum(item.get('total', 0) for item in line_items)

    # Get the total amount
    total_amount = extracted_data.get('total_amount', 0)

    # Check if calculated total matches extracted total (with small tolerance for rounding)
    tolerance = 0.05  # Allow for small rounding differences
    if abs(calculated_total - total_amount) > tolerance:
        errors.append(f"Math Mismatch: Sum of lines ({calculated_total}) != Total ({total_amount})")

    # Validate tax calculation if both tax and subtotal are present
    tax_amount = extracted_data.get('tax_amount', 0)
    if 'subtotal' in extracted_data:  # If subtotal is provided
        subtotal = extracted_data['subtotal']
        expected_total = subtotal + tax_amount
        if abs(expected_total - total_amount) > tolerance:
            errors.append(f"Tax Math Error: Subtotal ({subtotal}) + Tax ({tax_amount}) != Total ({total_amount})")

    # Check for required fields
    if not extracted_data.get('vendor_name'):
        errors.append("Missing required field: vendor_name")

    if extracted_data.get('total_amount', 0) == 0:
        errors.append("Missing or zero total_amount")

    return errors

def validate_null_checks(extracted_data: Dict[str, Any]) -> List[str]:
    """
    Validates that critical fields are not null/empty.
    Returns list of validation errors if any.
    """
    errors = []

    required_fields = ['vendor_name', 'total_amount']

    for field in required_fields:
        value = extracted_data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"Missing required field: {field}")

    return errors