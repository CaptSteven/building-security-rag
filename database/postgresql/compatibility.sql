CREATE TABLE IF NOT EXISTS compatibility (
id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
source_device_id bigint NOT NULL REFERENCES devices(id),
target_device_id bigint NOT NULL REFERENCES devices(id),
document_id bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
verdict text NOT NULL CHECK (verdict IN ('compatible','incompatible','conditional')),
conditions text NOT NULL, evidence_quote text NOT NULL,
UNIQUE(source_device_id,target_device_id,document_id),
CHECK(source_device_id <> target_device_id));
