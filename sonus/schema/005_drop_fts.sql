-- Drop FTS5 search index; library search uses LIKE on tracks columns instead.

DROP TRIGGER IF EXISTS tracks_fts_insert;
DROP TRIGGER IF EXISTS tracks_fts_delete;
DROP TRIGGER IF EXISTS tracks_fts_update;

DROP TABLE IF EXISTS tracks_fts;

INSERT INTO schema_version (version) VALUES (5);
