# Repository conventions

- Follow docs/project-structure.md and data/README.md.
- Keep frontend in frontend/, backend in backend/src/security_rag/, offline processing in pipelines/.
- Keep SQL and database files in database/, not application source or raw-data directories.
- Preserve originals under data/raw/pdfs/. Never clean, truncate, translate, or overwrite originals in place.
- Use a new run_id for new collection. Current manifest paths are relative to the repository root.
- Historical logs/code snapshots under logs/ are evidence, not active entrypoints; do not rewrite them.
- Record path migrations with old/new paths and hashes; update manifests, database metadata, docs and tests together.
- Keep fictional test fixtures separate from actual equipment knowledge; extracted text is not cleaned data.
- Run tests from the root: uv run --group collection pytest -q.
