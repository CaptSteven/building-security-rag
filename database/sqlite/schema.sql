CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    brand TEXT,
    model TEXT,
    category TEXT,
    source_page TEXT
);
CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    device_id TEXT REFERENCES devices(device_id),
    kind TEXT,
    title TEXT,
    status TEXT,
    path TEXT,
    sha256 TEXT,
    metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS pages (
    asset_id TEXT,
    page INTEGER,
    text TEXT,
    raw_sha256 TEXT,
    PRIMARY KEY (asset_id, page)
);
