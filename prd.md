# PRD: FREIGHTSTRUCTURIZE (Vertical AI Agent)

**Status:** PRODUCTION LOCKED
 **Role:** Automated Freight Auditor & Compliance Officer
 **Version:** 1.0.0

------

## 1. System Identity & Mission

**FreightStructurize** is an autonomous "Back-Office Agent" for 3PLs and Freight Brokers. It does not just OCR documents; it performs **forensic auditing** on every Bill of Lading (BoL) and Carrier Invoice.

**Mission:**

1. **Recover Revenue:** Catch carrier overcharges (Rate vs. Contract).
2. **Ensure Compliance:** Detect "bad redactions" (text leaks) in sensitive legal/freight docs.
3. **Automate Entry:** Sync validated data to TMS (Transportation Management System).

**The Promise:** "Forward the invoice. We find the lost money."

------

## 2. Vertical Workflow (The Invisible Loop)

## **Phase 1: Ingestion**

- **Trigger:** Email received at `invoices@freightstructurize.ai` (or client domain).
- **Filter:** Reject spam. Isolate PDF attachments.
- **Queue:** Push to Redis Job Queue (`job_id: uuid`).

## **Phase 2: The "Brain" (Extraction)**

- **OCR:** Convert PDF to Markdown (preserving table structures).
- **LLM Extraction:** Llama-3-70b extracts structured JSON:
  - `PRO_Number` (Tracking ID)
  - `Carrier_Name`
  - `Origin_Zip`, `Dest_Zip`
  - `Billable_Weight`
  - `Line_Haul_Rate`, `Fuel_Surcharge`, `Total_Amount`

## **Phase 3: The "Judge" (Validation Core)**

- **Rate Audit:**
  - Fetch `RateCard` for Carrier + Lane (Zip to Zip).
  - Calculate `Expected_Cost = (Weight * Contract_Rate) + Fuel`.
  - Compare `Invoice_Total` vs. `Expected_Cost`.
  - **Rule:** If `Invoice > Expected + 3%`, Flag as **OVERCHARGE**.
- **Redaction Audit (The "X-Ray"):**
  - Scan PDF for black vector rectangles.
  - Check for selectable text layers *underneath* or *near* rectangles.
  - **Rule:** If text exists under rectangle, Flag as **SECURITY_LEAK**.

## **Phase 4: Execution**

- **Success:** If Flags = 0, push JSON to TMS API (FreightBooks/Magaya).
- **Failure:** If Flags > 0, alert Slack channel `#audit-alerts` with "Overcharge Detected: $142.50" or "Compliance Risk: Failed Redaction".

------

## 3. Data Model (PostgreSQL / D1)

```
sql-- 1. Tenants (3PL Firms)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    tms_webhook_url TEXT
);

-- 2. The Rules (Contract Rates)
CREATE TABLE rate_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    carrier_name TEXT NOT NULL,
    origin_zone TEXT,
    dest_zone TEXT,
    min_weight INTEGER,
    max_weight INTEGER,
    rate_per_lb DECIMAL(10, 4),
    base_charge DECIMAL(10, 2),
    effective_date DATE,
    expiry_date DATE
);

-- 3. The Jobs (Audits)
CREATE TABLE audit_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    created_at TIMESTAMP DEFAULT NOW(),
    source_email TEXT,
    original_filename TEXT,
    
    -- Extracted Data
    pro_number TEXT,
    carrier_extracted TEXT,
    weight_extracted DECIMAL(10, 2),
    amount_invoiced DECIMAL(10, 2),
    
    -- Audit Results
    amount_calculated DECIMAL(10, 2),
    variance_amount DECIMAL(10, 2),
    is_overcharge BOOLEAN DEFAULT FALSE,
    has_bad_redaction BOOLEAN DEFAULT FALSE,
    
    -- Status
    status TEXT CHECK (status IN ('PROCESSING', 'APPROVED', 'FLAGGED', 'SYNCED'))
);

-- 4. Audit Trail (Logs)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    job_id UUID REFERENCES audit_jobs(id),
    log_level TEXT,
    message TEXT, -- e.g. "Rate card matching logic applied: Lane NYC->CHI"
    timestamp TIMESTAMP DEFAULT NOW()
);
```

------

## 4. The Core Engine (Python Code)

This is the production logic for Phase 3 (Validation). It assumes extraction has passed JSON data to this class.

**Dependencies:** `fitz` (PyMuPDF), `pandas`, `pydantic`.

```
pythonimport fitz  # PyMuPDF
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
    line_items: List[Dict]

class AuditResult(BaseModel):
    job_id: str
    is_compliant: bool
    flags: List[str]
    calculated_rate: float
    savings_identified: float
    security_risk: bool

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
                    
                    if overlap:
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
        base_cost = data.weight_lbs * rate_row['rate']
        
        # Hardcoded 15% Fuel Surcharge for MVP (External API in V2)
        total_expected = base_cost * 1.15 
        return round(total_expected, 2)

    def audit_shipment(self, pdf_path: str, data: InvoiceData, job_id: str) -> AuditResult:
        flags = []
        is_compliant = True
        security_risk = False
        savings = 0.0
        
        # Step 1: Security Audit
        if self.detect_bad_redactions(pdf_path):
            flags.append("CRITICAL: Bad Redaction Detected (Text Leak)")
            security_risk = True
            is_compliant = False
            
        # Step 2: Financial Audit
        try:
            expected = self.calculate_expected_cost(data)
            variance = data.total_amount - expected
            
            # Tolerance: If variance > $5.00 or > 2%
            if variance > 5.00 and (variance / expected) > 0.02:
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
            security_risk=security_risk
        )

# --- Execution Example (Mock) ---

if __name__ == "__main__":
    # 1. Load Rate Cards (In-Memory for MVP)
    rates_data = {
        'carrier': ['FedEx_Freight', 'XPO_Logistics'],
        'origin_zone': ['100', '902'], # NYC, LA
        'dest_zone': ['606', '331'],   # CHI, MIA
        'min_w': [0, 0],
        'max_w': [10000, 10000],
        'rate': [0.45, 0.55] # Cents per lb
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

    # 3. Run Audit
    # Assuming 'test_invoice.pdf' exists locally
    # result = auditor.audit_shipment("test_invoice.pdf", invoice, "job_123")
    
    # print(result.json(indent=2))
```

------

## 5. Implementation Notes (Zero-Ambiguity)

1. **PDF Redaction Logic:** The code uses `PyMuPDF` (fitz). It detects drawings (black rectangles) and checks intersection with text layers. This is the exact mechanism "X-Ray" tools use to find leaks.
2. **Rate Logic:** The `pandas` DataFrame acts as the in-memory cache of the SQL `rate_cards` table. In production, load this from Redis for speed.
3. **Fuel Surcharge:** The code uses a flat 1.15 multiplier. In production, fetch weekly DOE (Dept of Energy) fuel averages to adjust this dynamically.
4. **Integration:** The `FreightAuditor` class is designed to be called by a Celery/Redis worker processing the job queue.
5. **Output:** The `AuditResult` object is what gets saved to the `audit_jobs` table in PostgreSQL. Flags are serialized to JSON.

