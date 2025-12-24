CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  structurize_email TEXT UNIQUE NOT NULL,
  google_refresh_token TEXT NOT NULL,
  plan TEXT DEFAULT 'starter' CHECK (plan IN ('starter', 'pro', 'agency')),
  created_at INTEGER NOT NULL
);

CREATE TABLE extractors (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  trigger_keywords TEXT[],
  target_sheet_id TEXT NOT NULL,
  schema_json TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  extractor_id TEXT,
  r2_key TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  extracted_json TEXT,
  audit_flags TEXT,
  confidence_score REAL,
  error TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id),
  FOREIGN KEY(extractor_id) REFERENCES extractors(id)
);

CREATE TABLE historical_invoices (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  vendor_name TEXT NOT NULL,
  invoice_number TEXT,
  total_amount REAL,
  invoice_date TEXT,
  created_at INTEGER,
  job_id TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX idx_vendor_history ON historical_invoices(user_id, vendor_name);
CREATE INDEX idx_jobs_user ON jobs(user_id);