-- Sonus initial schema (version 1)
--
-- One row per audio file on disk. Metadata fields are nullable because
-- extractors vary by format and file quality.

PRAGMA foreign_keys = ON;

CREATE TABLE schema_version (
    version     INTEGER NOT NULL PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE tracks (
    id              INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,

    file_path       TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    format          TEXT NOT NULL CHECK (format IN ('mp3', 'flac', 'ogg', 'opus', 'm4a', 'aac', 'wav', 'wma')),
    file_size       INTEGER NOT NULL CHECK (file_size >= 0),
    file_mtime      REAL NOT NULL,
    content_hash    TEXT,

    title           TEXT,
    sort_title      TEXT,
    artist          TEXT,
    album           TEXT,
    album_artist    TEXT,
    track_number    INTEGER,
    disc_number     INTEGER,
    year            TEXT,
    genre           TEXT,
    duration_seconds REAL CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    art_path        TEXT,

    first_seen_at   TEXT NOT NULL,
    last_scanned_at TEXT NOT NULL,
    is_missing      INTEGER NOT NULL DEFAULT 0 CHECK (is_missing IN (0, 1)),

    UNIQUE (file_path)
);

CREATE INDEX idx_tracks_title ON tracks (title COLLATE NOCASE);
CREATE INDEX idx_tracks_sort_title ON tracks (sort_title COLLATE NOCASE);
CREATE INDEX idx_tracks_artist ON tracks (artist COLLATE NOCASE);
CREATE INDEX idx_tracks_album ON tracks (album COLLATE NOCASE);
CREATE INDEX idx_tracks_album_artist ON tracks (album_artist COLLATE NOCASE);
CREATE INDEX idx_tracks_genre ON tracks (genre COLLATE NOCASE);
CREATE INDEX idx_tracks_format ON tracks (format);
CREATE INDEX idx_tracks_last_scanned ON tracks (last_scanned_at);
CREATE INDEX idx_tracks_is_missing ON tracks (is_missing);

CREATE VIRTUAL TABLE tracks_fts USING fts5 (
    title,
    artist,
    album,
    album_artist,
    genre,
    file_name,
    content='tracks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER tracks_fts_insert
AFTER INSERT ON tracks
BEGIN
    INSERT INTO tracks_fts (
        rowid, title, artist, album, album_artist, genre, file_name
    ) VALUES (
        new.id, new.title, new.artist, new.album, new.album_artist, new.genre, new.file_name
    );
END;

CREATE TRIGGER tracks_fts_delete
AFTER DELETE ON tracks
BEGIN
    INSERT INTO tracks_fts (
        tracks_fts, rowid, title, artist, album, album_artist, genre, file_name
    ) VALUES (
        'delete', old.id, old.title, old.artist, old.album, old.album_artist, old.genre, old.file_name
    );
END;

CREATE TRIGGER tracks_fts_update
AFTER UPDATE ON tracks
BEGIN
    INSERT INTO tracks_fts (
        tracks_fts, rowid, title, artist, album, album_artist, genre, file_name
    ) VALUES (
        'delete', old.id, old.title, old.artist, old.album, old.album_artist, old.genre, old.file_name
    );
    INSERT INTO tracks_fts (
        rowid, title, artist, album, album_artist, genre, file_name
    ) VALUES (
        new.id, new.title, new.artist, new.album, new.album_artist, new.genre, new.file_name
    );
END;

INSERT INTO schema_version (version) VALUES (1);
