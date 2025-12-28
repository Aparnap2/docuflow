from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class LineItem(BaseModel):
    description: str = Field(default="", description="Item name or description")
    quantity: float = Field(default=0.0, description="Count/Qty")
    unit_price: float = Field(default=0.0, description="Price per unit")
    total: float = Field(default=0.0, description="Line total")

class ExtractedData(BaseModel):
    # Core Fields
    vendor_name: Optional[str] = Field(None, description="Name of the supplier/vendor")
    invoice_date: Optional[str] = Field(None, description="YYYY-MM-DD format")
    invoice_number: Optional[str] = Field(None, description="Invoice ID")
    currency: str = Field(default="USD", description="Currency Code (USD, EUR)")
    tax_amount: float = Field(default=0.0, description="Total Tax/VAT")
    total_amount: float = Field(default=0.0, description="Final Total Due")
    line_items: List[LineItem] = Field(default_factory=list)

    # Dynamic Fields (for custom schemas)
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # Metadata for Agent
    validation_warnings: List[str] = Field(default_factory=list)
    is_valid: bool = Field(default=True)