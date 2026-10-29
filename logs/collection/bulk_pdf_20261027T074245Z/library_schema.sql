PRAGMA foreign_keys=ON;
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    manifest_path TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL
);
CREATE TABLE devices (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    device_id TEXT NOT NULL,
    brand TEXT,
    model TEXT,
    category TEXT,
    source_page TEXT,
    PRIMARY KEY(run_id,device_id)
);
CREATE TABLE assets (
    run_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    kind TEXT,
    title TEXT,
    status TEXT NOT NULL,
    path TEXT,
    sha256 TEXT,
    byte_size INTEGER,
    page_count INTEGER,
    source_url TEXT,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY(run_id,asset_id),
    FOREIGN KEY(run_id,device_id) REFERENCES devices(run_id,device_id)
);
CREATE TABLE pages (
    run_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    page INTEGER NOT NULL,
    text TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL,
    PRIMARY KEY(run_id,asset_id,page),
    FOREIGN KEY(run_id,asset_id) REFERENCES assets(run_id,asset_id)
);
CREATE INDEX assets_status_idx ON assets(status);
CREATE INDEX assets_sha256_idx ON assets(sha256);
CREATE VIEW downloaded_pdfs AS
SELECT a.*,d.brand,d.model,d.category,d.source_page
FROM assets a JOIN devices d USING(run_id,device_id)
WHERE a.status='downloaded' AND lower(a.path) LIKE '%.pdf';
