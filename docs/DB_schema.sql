-- MVP schema, соответствует SQLAlchemy моделям в `backend/app/models.py`

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  age INTEGER,
  gender VARCHAR(20),
  language VARCHAR(10) DEFAULT 'ru',
  created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

CREATE TABLE IF NOT EXISTS analyses (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  source VARCHAR(20) DEFAULT 'web',
  format VARCHAR(100) DEFAULT 'file',
  status VARCHAR(20) DEFAULT 'received',
  document_ref VARCHAR(255),
  ocr_text TEXT
);

CREATE INDEX IF NOT EXISTS ix_analyses_user_id ON analyses(user_id);

CREATE TABLE IF NOT EXISTS test_indicators (
  id SERIAL PRIMARY KEY,
  analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  test_name VARCHAR(255) NOT NULL,
  value NUMERIC(18,6),
  units VARCHAR(50),
  ref_min NUMERIC(18,6),
  ref_max NUMERIC(18,6),
  deviation VARCHAR(10),
  comment TEXT
);

CREATE INDEX IF NOT EXISTS ix_test_indicators_analysis_id ON test_indicators(analysis_id);

