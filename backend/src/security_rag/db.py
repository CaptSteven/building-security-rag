import psycopg
from psycopg.rows import dict_row
from .config import PROJECT_ROOT, Settings

SCHEMA_DIR = PROJECT_ROOT / "database/postgresql"


def connect(config: Settings):
    return psycopg.connect(config.database_url, row_factory=dict_row, connect_timeout=5,
                           options="-c statement_timeout=15000")


def init_db(config: Settings):
    with connect(config) as conn:
        conn.execute((SCHEMA_DIR / "bootstrap.sql").read_text())
        conn.execute("INSERT INTO kb_settings VALUES ('embedding_space', %s) ON CONFLICT DO NOTHING",
                     (config.embedding_space,))
        assert_space(conn, config)
        sql = (SCHEMA_DIR / "schema.sql").read_text().replace("__EMBEDDING_DIM__", str(config.embedding_dim))
        conn.execute(sql)


def assert_space(conn, config: Settings):
    row = conn.execute("SELECT value FROM kb_settings WHERE key='embedding_space'").fetchone()
    if not row or row["value"] != config.embedding_space:
        raise ValueError("向量空间不匹配：更换模型或维度请创建新库并重新入库")


def init_compatibility(config: Settings):
    with connect(config) as conn:
        conn.execute((SCHEMA_DIR / "compatibility.sql").read_text())
