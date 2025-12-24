"""
Freight Auditor - Core validation engine for FreightStructurize
Implements rate validation and bad redaction detection as per PRD
"""
import fitz  # PyMuPDF
import pandas as pd
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime


# --- Data Structures ---

class InvoiceData(BaseModel):
    pro_number: str
    carrier: str
    origin_zip: str
    dest_zip: str
    weight_lbs: float
    total_amount: float
    line_haul_rate: Optional[float] = None
    fuel_surcharge: Optional[float] = None
    line_items: List[Dict] = []


class AuditResult(BaseModel):
    job_id: str
    is_compliant: bool
    flags: List[str]
    calculated_rate: float
    savings_identified: float
    security_risk: bool
    expected_cost: float = 0.0


# --- The Engine ---

class FreightAuditor:
    def __init__(self, rate_card_df: pd.DataFrame):
        """
        rate_card_df columns: ['carrier', 'origin_zone', 'dest_zone', 'min_w', 'max_w', 'rate']
        """
        self.rates = rate_card_df

    def detect_bad_redactions(self, pdf_path: str) -> bool:
        """
        Scans PDF for 'Lazy Redaction' where text exists under black boxes.
        Returns True if a security risk is found.
        """
        doc = fitz.open(pdf_path)
        risk_detected = False

        for page in doc:
            # 1. Find vector drawings (rectangles) that are black/dark
            drawings = [
                d for d in page.get_drawings()
                if d['fill'] and sum(d['fill']) < 0.5  # Assuming dark fill
            ]

            # 2. Extract text words with their bounding boxes
            words = page.get_text("words")  # (x0, y0, x1, y1, "text", ...)

            for rect in drawings:
                rx0, ry0, rx1, ry1 = rect['rect']

                # Check if any word is technically 'inside' or overlapping the black box
                for w in words:
                    wx0, wy0, wx1, wy1, text = w[:5]

                    # Intersection logic
                    overlap = not (wx1 < rx0 or wx0 > rx1 or wy1 < ry0 or wy0 > ry1)

                    if overlap and text.strip():
                        # If text is selectable/extractable but covered by draw, it's a LEAK.
                        print(f"SECURITY ALERT: Text '{text}' found under redaction on page {page.number}")
                        risk_detected = True
                        break

            if risk_detected:
                break

        doc.close()
        return risk_detected

    def calculate_expected_cost(self, data: InvoiceData) -> float:
        """
        Matches Carrier + Lane + Weight against loaded Rate Cards.
        """
        # 1. Filter by Carrier
        carrier_rates = self.rates[self.rates['carrier'] == data.carrier]

        # 2. Filter by Zone (Simplified Zip matching)
        # In prod, use a dedicated Zone Lookup Table
        lane_rates = carrier_rates[
            (carrier_rates['origin_zone'] == data.origin_zip[:3]) &
            (carrier_rates['dest_zone'] == data.dest_zip[:3])
        ]

        # 3. Filter by Weight Break
        valid_rate = lane_rates[
            (lane_rates['min_w'] <= data.weight_lbs) &
            (lane_rates['max_w'] >= data.weight_lbs)
        ]

        if valid_rate.empty:
            raise ValueError(f"No contract rate found for {data.carrier} on lane {data.origin_zip}->{data.dest_zip}")

        rate_row = valid_rate.iloc[0]
        base_cost = data.weight_lbs * rate_row['rate']  # Using 'rate' column from sample data

        # Hardcoded 15% Fuel Surcharge for MVP (External API in V2)
        total_expected = base_cost * 1.15
        return round(total_expected, 2)

    def audit_shipment(self, pdf_path: str, data: InvoiceData, job_id: str) -> AuditResult:
        flags = []
        is_compliant = True
        security_risk = False
        savings = 0.0
        expected = 0.0

        # Step 1: Security Audit
        if self.detect_bad_redactions(pdf_path):
            flags.append("CRITICAL: Bad Redaction Detected (Text Leak)")
            security_risk = True
            is_compliant = False

        # Step 2: Financial Audit
        try:
            expected = self.calculate_expected_cost(data)
            variance = data.total_amount - expected

            # Tolerance: If variance > $5.00 or > 3%
            if variance > 5.00 and (variance / expected) > 0.03:
                flags.append(f"OVERCHARGE: Invoiced ${data.total_amount}, Contract ${expected}")
                savings = variance
                is_compliant = False

        except ValueError as e:
            flags.append(f"RATE_MISSING: {str(e)}")
            expected = 0.0
            is_compliant = False

        return AuditResult(
            job_id=job_id,
            is_compliant=is_compliant,
            flags=flags,
            calculated_rate=expected,
            savings_identified=savings,
            security_risk=security_risk,
            expected_cost=expected
        )


if __name__ == "__main__":
    # 1. Load Rate Cards (In-Memory for MVP)
    rates_data = {
        'carrier': ['FedEx_Freight', 'XPO_Logistics'],
        'origin_zone': ['100', '902'], # NYC, LA
        'dest_zone': ['606', '331'],   # CHI, MIA
        'min_w': [0, 0],
        'max_w': [10000, 10000],
        'rate': [0.45, 0.55] # Dollars per lb
    }
    df = pd.DataFrame(rates_data)
    auditor = FreightAuditor(df)

    # 2. Mock Extracted Data (From Llama 3)
    invoice = InvoiceData(
        pro_number="PRO-998877",
        carrier="FedEx_Freight",
        origin_zip="10001",
        dest_zip="60601",
        weight_lbs=2500,
        total_amount=1450.00, # Expected: ~1293.75 (2500 * .45 * 1.15) -> Overcharge
        line_items=[]
    )

    print("FreightAuditor initialized with sample rate data")
    print(f"Sample invoice: {invoice.pro_number} for {invoice.carrier}")
    print(f"Route: {invoice.origin_zip} -> {invoice.dest_zip}, Weight: {invoice.weight_lbs} lbs")
    print(f"Invoiced amount: ${invoice.total_amount}")