-- User accounts and per-user playlists (version 3)

PRAGMA foreign_keys = OFF;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE playlists_new (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, name)
);

CREATE TABLE playlist_tracks_new (
    playlist_id INTEGER NOT NULL REFERENCES playlists_new(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (playlist_id, track_id)
);

DROP TABLE IF EXISTS playlist_tracks;
DROP TABLE IF EXISTS playlists;

ALTER TABLE playlists_new RENAME TO playlists;
ALTER TABLE playlist_tracks_new RENAME TO playlist_tracks;

CREATE INDEX idx_playlist_tracks_order ON playlist_tracks (playlist_id, position);
CREATE INDEX idx_playlists_user ON playlists (user_id);

PRAGMA foreign_keys = ON;

INSERT INTO schema_version (version) VALUES (3);
