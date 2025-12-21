-- DocuFlow v2.0 Enhanced D1 Schema
-- Hybrid search foundation with keyword support and rich metadata

-- Drop existing tables if they exist (for clean migration)
DROP TABLE IF EXISTS chunks;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS projects;

-- Projects table (unchanged)
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

-- Documents table with enhanced indexing
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_name TEXT NOT NULL,
  content_type TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  r2_key TEXT,
  status TEXT NOT NULL CHECK (status IN ('CREATED', 'PROCESSING', 'READY', 'FAILED')),
  chunk_count INTEGER DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Enhanced chunks table with hybrid search support
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  content_md TEXT NOT NULL,
  keywords TEXT, -- Space-separated keywords for keyword search
  metadata_key TEXT, -- R2 key for rich metadata storage
  page_number INTEGER, -- Page number for citations
  section_hierarchy TEXT, -- JSON array of section headers
  created_at INTEGER NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- Create indexes for performance
CREATE INDEX idx_documents_project_id ON documents(project_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_sha256 ON documents(sha256);
CREATE INDEX idx_chunks_project_id ON chunks(project_id);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_keywords ON chunks(keywords);
CREATE INDEX idx_chunks_page_number ON chunks(page_number);

-- Create a virtual table for full-text search (D1 doesn't support FTS, so we use LIKE)
-- We'll implement keyword extraction in application code
CREATE INDEX idx_chunks_content ON chunks(content_md);

-- Insert sample data for testing
INSERT INTO projects (id, name, created_at, updated_at) VALUES 
('test-project-1', 'Test Project', 1704067200000, 1704067200000);

INSERT INTO documents (id, project_id, source_name, content_type, sha256, r2_key, status, chunk_count, created_at, updated_at) VALUES 
('doc-1', 'test-project-1', 'test.pdf', 'application/pdf', 'abc123', 'docs/test.pdf', 'READY', 5, 1704067200000, 1704067200000);

INSERT INTO chunks (id, project_id, document_id, chunk_index, content_md, keywords, metadata_key, page_number, section_hierarchy, created_at) VALUES 
('chunk-1', 'test-project-1', 'doc-1', 0, 'This is a test chunk about termination fees and contract cancellation.', 'termination fees contract cancellation', 'metadata/chunk-1.json', 1, '["Introduction", "Contract Terms"]', 1704067200000),
('chunk-2', 'test-project-1', 'doc-1', 1, 'The cancellation policy requires 30 days notice and may incur additional charges.', 'cancellation policy notice charges', 'metadata/chunk-2.json', 2, '["Introduction", "Contract Terms", "Cancellation"]', 1704067200000),
('chunk-3', 'test-project-1', 'doc-1', 2, 'Table showing fee structure: Basic plan $10/month, Premium plan $25/month.', 'table fee structure basic premium', 'metadata/chunk-3.json', 3, '["Pricing", "Fee Structure"]', 1704067200000);

-- Create a view for hybrid search results
CREATE VIEW hybrid_search_view AS
SELECT 
  c.id,
  c.project_id,
  c.document_id,
  c.chunk_index,
  c.content_md,
  c.keywords,
  c.metadata_key,
  c.page_number,
  c.section_hierarchy,
  c.created_at,
  d.source_name,
  d.sha256,
  d.status as document_status
FROM chunks c
JOIN documents d ON c.document_id = d.id
WHERE d.status = 'READY';

-- Create a function to extract keywords (simulated)
-- In real implementation, this will be done in application code
-- This is just for demonstration
CREATE TABLE keyword_extraction_rules (
  rule_name TEXT PRIMARY KEY,
  pattern TEXT NOT NULL,
  description TEXT
);

INSERT INTO keyword_extraction_rules (rule_name, pattern, description) VALUES 
('remove_stopwords', 'the|and|or|but|in|on|at|to|for|of|with|by|from|up|about|into|through|during|before|after|above|below|between|among|through|during|before|after|above|below|between|among', 'Remove common stop words'),
('extract_long_words', '[a-zA-Z]{4,}', 'Extract words with 4+ characters'),
('extract_numbers', '\d+', 'Extract numbers');

-- Create a table to track processing metrics
CREATE TABLE processing_metrics (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  processing_time_ms INTEGER,
  chunk_count INTEGER,
  embedding_time_ms INTEGER,
  vectorize_time_ms INTEGER,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id)
);

-- Create a table for search analytics
CREATE TABLE search_analytics (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  query TEXT NOT NULL,
  query_type TEXT NOT NULL CHECK (query_type IN ('keyword', 'semantic', 'hybrid')),
  result_count INTEGER,
  latency_ms INTEGER,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Create indexes for analytics
CREATE INDEX idx_processing_metrics_document_id ON processing_metrics(document_id);
CREATE INDEX idx_search_analytics_project_id ON search_analytics(project_id);
CREATE INDEX idx_search_analytics_created_at ON search_analytics(created_at);

-- Add comments for documentation
COMMENT ON TABLE chunks IS 'Document chunks with hybrid search support';
COMMENT ON TABLE documents IS 'Documents with enhanced metadata and status tracking';
COMMENT ON TABLE projects IS 'Project organization and management';
COMMENT ON TABLE processing_metrics IS 'Performance metrics for document processing';
COMMENT ON TABLE search_analytics IS 'Search query analytics for optimization';