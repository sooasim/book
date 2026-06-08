CREATE TABLE IF NOT EXISTS books (
  book_id TEXT PRIMARY KEY,
  title TEXT,
  author TEXT,
  genre TEXT,
  source_format TEXT,
  source_hash TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS pages (
  page_id TEXT PRIMARY KEY,
  book_id TEXT,
  page_number INTEGER,
  chapter_id TEXT,
  raw_text TEXT,
  normalized_text TEXT,
  source_hash TEXT,
  output_hash TEXT,
  status TEXT
);

CREATE TABLE IF NOT EXISTS blocks (
  block_id TEXT PRIMARY KEY,
  book_id TEXT,
  page_id TEXT,
  order_index INTEGER,
  block_type TEXT,
  raw_text TEXT,
  polished_text TEXT,
  source_hash TEXT,
  status TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id TEXT PRIMARY KEY,
  book_id TEXT,
  page_start INTEGER,
  page_end INTEGER,
  primary_block_ids TEXT,
  overlap_block_ids TEXT,
  token_estimate INTEGER,
  status TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
  event_id TEXT PRIMARY KEY,
  book_id TEXT,
  target_id TEXT,
  event_type TEXT,
  before_hash TEXT,
  after_hash TEXT,
  payload_json TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS memory_items (
  memory_id TEXT PRIMARY KEY,
  book_id TEXT,
  layer INTEGER,
  memory_type TEXT,
  content TEXT,
  importance REAL,
  tags TEXT
);
