-- Scale improvements (version 4): content_hash index and FTS sort_title column

CREATE INDEX IF NOT EXISTS idx_tracks_content_hash ON tracks (content_hash);

DROP TRIGGER IF EXISTS tracks_fts_insert;
DROP TRIGGER IF EXISTS tracks_fts_delete;
DROP TRIGGER IF EXISTS tracks_fts_update;

DROP TABLE IF EXISTS tracks_fts;

CREATE VIRTUAL TABLE tracks_fts USING fts5 (
    title,
    sort_title,
    artist,
    album,
    album_artist,
    genre,
    file_name,
    content='tracks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

INSERT INTO tracks_fts (
    rowid, title, sort_title, artist, album, album_artist, genre, file_name
)
SELECT id, title, sort_title, artist, album, album_artist, genre, file_name
FROM tracks;

CREATE TRIGGER tracks_fts_insert
AFTER INSERT ON tracks
BEGIN
    INSERT INTO tracks_fts (
        rowid, title, sort_title, artist, album, album_artist, genre, file_name
    ) VALUES (
        new.id, new.title, new.sort_title, new.artist, new.album, new.album_artist, new.genre, new.file_name
    );
END;

CREATE TRIGGER tracks_fts_delete
AFTER DELETE ON tracks
BEGIN
    INSERT INTO tracks_fts (
        tracks_fts, rowid, title, sort_title, artist, album, album_artist, genre, file_name
    ) VALUES (
        'delete', old.id, old.title, old.sort_title, old.artist, old.album, old.album_artist, old.genre, old.file_name
    );
END;

CREATE TRIGGER tracks_fts_update
AFTER UPDATE ON tracks
BEGIN
    INSERT INTO tracks_fts (
        tracks_fts, rowid, title, sort_title, artist, album, album_artist, genre, file_name
    ) VALUES (
        'delete', old.id, old.title, old.sort_title, old.artist, old.album, old.album_artist, old.genre, old.file_name
    );
    INSERT INTO tracks_fts (
        rowid, title, sort_title, artist, album, album_artist, genre, file_name
    ) VALUES (
        new.id, new.title, new.sort_title, new.artist, new.album, new.album_artist, new.genre, new.file_name
    );
END;

INSERT INTO schema_version (version) VALUES (4);
