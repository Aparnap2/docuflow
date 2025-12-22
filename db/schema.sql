PRAGMA foreign_keys = ON;

-- Users table for authentication and billing
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    plan TEXT DEFAULT 'starter' CHECK (plan IN ('starter', 'pro', 'agency')),
    structurize_email TEXT UNIQUE, -- e.g. user_123@structurize.ai
    google_access_token TEXT,
    google_refresh_token TEXT,
    google_sheets_config TEXT, -- JSON with selected sheet info
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Extractors table for custom schema definitions (per PRD)
CREATE TABLE IF NOT EXISTS extractors (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL, -- e.g. "Invoices", "Resumes"
    trigger_subject TEXT, -- e.g. "Invoice", "Application" (to route emails)
    target_sheet_id TEXT, -- specific sheet for this extractor type
    schema_json TEXT NOT NULL, -- JSON schema definition
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Jobs table to track email processing jobs
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    r2_key TEXT NOT NULL, -- path to stored attachment in R2
    original_name TEXT NOT NULL,
    sender TEXT NOT NULL,
    extractor_id TEXT, -- NULL if auto-detected
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    extracted_data TEXT, -- JSON with extracted fields
    error_message TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    completed_at INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(extractor_id) REFERENCES extractors(id)
);

-- Billing table for LemonSqueezy integration
CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    lemonsqueezy_id TEXT NOT NULL,
    plan TEXT NOT NULL CHECK (plan IN ('starter', 'pro', 'agency')),
    status TEXT NOT NULL CHECK (status IN ('active', 'cancelled', 'expired')),
    renews_at INTEGER,
    ends_at INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);</parameter>
</execute_command>