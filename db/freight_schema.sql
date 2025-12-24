-- FreightStructurize Database Schema
-- PostgreSQL schema for freight auditing system

-- 1. Tenants (3PL Firms)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    tms_webhook_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
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
    expiry_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 3. The Jobs (Audits) - updated version with freight-specific fields
CREATE TABLE audit_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    created_at TIMESTAMP DEFAULT NOW(),
    source_email TEXT,
    original_filename TEXT,

    -- Extracted Data
    pro_number TEXT,
    carrier_extracted TEXT,
    origin_zip TEXT,
    dest_zip TEXT,
    weight_extracted DECIMAL(10, 2),
    line_haul_rate DECIMAL(10, 2),
    fuel_surcharge DECIMAL(10, 2),
    total_amount DECIMAL(10, 2),

    -- Audit Results
    amount_calculated DECIMAL(10, 2),
    variance_amount DECIMAL(10, 2),
    is_overcharge BOOLEAN DEFAULT FALSE,
    has_bad_redaction BOOLEAN DEFAULT FALSE,

    -- Status
    status TEXT CHECK (status IN ('PROCESSING', 'APPROVED', 'FLAGGED', 'SYNCED', 'FAILED')),
    
    -- Additional fields
    error_message TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 4. Audit Trail (Logs)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES audit_jobs(id),
    log_level TEXT,
    message TEXT, -- e.g. "Rate card matching logic applied: Lane NYC->CHI"
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_audit_jobs_org_id ON audit_jobs(org_id);
CREATE INDEX idx_audit_jobs_status ON audit_jobs(status);
CREATE INDEX idx_audit_jobs_pro_number ON audit_jobs(pro_number);
CREATE INDEX idx_audit_jobs_carrier_extracted ON audit_jobs(carrier_extracted);
CREATE INDEX idx_rate_cards_org_id ON rate_cards(org_id);
CREATE INDEX idx_rate_cards_carrier ON rate_cards(carrier_name);
CREATE INDEX idx_audit_logs_job_id ON audit_logs(job_id);