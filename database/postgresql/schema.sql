CREATE TABLE IF NOT EXISTS devices (
id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
brand text NOT NULL, model text NOT NULL, category text NOT NULL,
UNIQUE (brand, model));

CREATE TABLE IF NOT EXISTS documents (
id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
source_key text UNIQUE NOT NULL, title text NOT NULL, source_url text,
version text NOT NULL, published_on date,
device_id bigint NOT NULL REFERENCES devices(id),
protocols jsonb NOT NULL, specs jsonb NOT NULL,
review_status text NOT NULL CHECK (review_status IN ('pending','verified','demo')),
content_hash text NOT NULL, ingested_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS chunks (
id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
document_id bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
ordinal integer NOT NULL, page integer, content text NOT NULL,
embedding vector(__EMBEDDING_DIM__) NOT NULL,
UNIQUE(document_id, ordinal));

CREATE INDEX IF NOT EXISTS chunks_document_idx ON chunks(document_id);

CREATE INDEX IF NOT EXISTS documents_specs_idx ON documents USING gin(specs);

CREATE INDEX IF NOT EXISTS documents_protocols_idx ON documents USING gin(protocols);

CREATE INDEX IF NOT EXISTS chunks_vector_idx ON chunks USING hnsw (embedding vector_cosine_ops);
