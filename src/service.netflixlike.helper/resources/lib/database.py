# -*- coding: utf-8 -*-
# Module: database
# Author: NetflixLike Project
# License: GPL v3.0

import xbmcvfs
import json
import os
import sqlite3
import time
import xbmcaddon


class Database:
    """Simple SQLite database for persistent storage."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.conn = None

    def init(self):
        """Initialize database connection and create tables."""
        if self.conn:
            return

        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # My List table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS my_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ffid TEXT UNIQUE NOT NULL,
                title TEXT,
                mediatype TEXT DEFAULT 'movie',
                added INTEGER,
                data TEXT
            )
        ''')

        # Continue watching table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS continue_watching (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ffid TEXT UNIQUE NOT NULL,
                title TEXT,
                mediatype TEXT,
                season INTEGER,
                episode INTEGER,
                progress REAL,
                total_time INTEGER,
                last_played INTEGER,
                source TEXT,
                data TEXT
            )
        ''')

        # Profiles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                name TEXT PRIMARY KEY,
                is_active INTEGER DEFAULT 0,
                created INTEGER,
                data TEXT
            )
        ''')

        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        self.conn.commit()

    @property
    def db_file(self):
        addon = xbmcaddon.Addon()
        profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        return os.path.join(profile_path, 'database.db')

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    # My List methods
    def mylist_add(self, ffid, title='', mediatype='movie', data=None):
        """Add item to my list."""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO my_list (ffid, title, mediatype, added, data)
                VALUES (?, ?, ?, ?, ?)
            ''', (ffid, title, mediatype, int(time.time()), json.dumps(data) if data else None))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def mylist_remove(self, ffid):
        """Remove item from my list."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM my_list WHERE ffid = ?', (ffid,))
        self.conn.commit()
        return cursor.rowcount > 0

    def mylist_get_all(self, limit=None):
        """Get all items from my list."""
        cursor = self.conn.cursor()
        query = 'SELECT * FROM my_list ORDER BY added DESC'
        if limit:
            query += f' LIMIT {limit}'
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    # Continue watching methods
    def cw_add(self, ffid, title='', mediatype='movie', season=0, episode=0,
               progress=0, total_time=0, source='kodi', data=None):
        """Add or update continue watching item."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO continue_watching
            (ffid, title, mediatype, season, episode, progress, total_time, last_played, source, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ffid, title, mediatype, season, episode, progress, total_time,
              int(time.time()), source, json.dumps(data) if data else None))
        self.conn.commit()

    def cw_get_all(self, limit=None):
        """Get all continue watching items."""
        cursor = self.conn.cursor()
        query = 'SELECT * FROM continue_watching ORDER BY last_played DESC'
        if limit:
            query += f' LIMIT {limit}'
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def cw_remove(self, ffid):
        """Remove from continue watching."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM continue_watching WHERE ffid = ?', (ffid,))
        self.conn.commit()
        return cursor.rowcount > 0

    # Profile methods
    def profile_get_all(self):
        """Get all profiles."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM profiles ORDER BY is_active DESC, name')
        return [dict(row) for row in cursor.fetchall()]

    def profile_set_active(self, name):
        """Set active profile."""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE profiles SET is_active = 0')
        cursor.execute('UPDATE profiles SET is_active = 1 WHERE name = ?', (name,))
        self.conn.commit()

    def profile_add(self, name):
        """Add new profile."""
        cursor = self.conn.cursor()
        try:
            cursor.execute('INSERT INTO profiles (name, is_active, created) VALUES (?, 0, ?)',
                           (name, int(time.time())))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    # Settings methods
    def setting_get(self, key, default=None):
        """Get setting value."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else default

    def setting_set(self, key, value):
        """Set setting value."""
        cursor = self.conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        self.conn.commit()