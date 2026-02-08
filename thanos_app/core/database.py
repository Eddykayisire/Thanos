# thanos_app/core/database.py
import sqlite3
from typing import List, Dict, Any, Optional
from config import VAULT_DB_FILE

class DatabaseManager:
    def __init__(self, db_file=VAULT_DB_FILE):
        self.db_file = db_file
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            self.conn.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create_tables(self):
        if not self.conn: self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vault_config (
            key TEXT PRIMARY KEY,
            value BLOB NOT NULL
        )
        """)

        # Ajout des colonnes category, importance, tags
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT,
            encrypted_password BLOB NOT NULL,
            url TEXT,
            notes TEXT,
            category TEXT DEFAULT 'Autre',
            importance INTEGER DEFAULT 1,
            tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.conn.commit()

    def create_logs_table(self):
        if not self.conn: self.connect()
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            encrypted_log_data BLOB NOT NULL
        )""")
        self.conn.commit()

    def migrate_database(self):
        """Vérifie et met à jour le schéma de la base de données si nécessaire."""
        if not self.conn: self.connect()
        cursor = self.conn.cursor()

        cursor.execute("PRAGMA table_info(accounts)")
        columns = [row['name'] for row in cursor.fetchall()]

        migrated = False
        if 'category' not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN category TEXT DEFAULT 'Autre'")
            migrated = True
        if 'importance' not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN importance INTEGER DEFAULT 1")
            migrated = True
        if 'tags' not in columns:
            cursor.execute("ALTER TABLE accounts ADD COLUMN tags TEXT DEFAULT ''")
            migrated = True

        if migrated:
            self.conn.commit()

    def add_log_entry(self, encrypted_log_data: bytes):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO security_logs (encrypted_log_data) VALUES (?)", (encrypted_log_data,))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_logs(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM security_logs ORDER BY timestamp DESC")
        return [dict(row) for row in cursor.fetchall()]

    def delete_old_logs(self, hours: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM security_logs WHERE timestamp < datetime('now', ?)", (f'-{hours} hours',))
        self.conn.commit()
        return cursor.rowcount

    def delete_log(self, log_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM security_logs WHERE id = ?", (log_id,))
        self.conn.commit()

    def add_account(self, name: str, username: str, encrypted_password: bytes, url: str, notes: str, category: str, importance: int, tags: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO accounts (name, username, encrypted_password, url, notes, category, importance, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, username, encrypted_password, url, notes, category, importance, tags)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        # Tri par importance (descendant) puis par nom
        cursor.execute("SELECT * FROM accounts ORDER BY importance DESC, name ASC")
        return [dict(row) for row in cursor.fetchall()]

    def get_account(self, account_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_account(self, account_id: int, name: str, username: str, encrypted_password: bytes, url: str, notes: str, category: str, importance: int, tags: str):
        cursor = self.conn.cursor()
        cursor.execute("""UPDATE accounts SET name=?, username=?, encrypted_password=?, url=?, notes=?, category=?, importance=?, tags=? WHERE id=?""",
            (name, username, encrypted_password, url, notes, category, importance, tags, account_id))
        self.conn.commit()

    def delete_account(self, account_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.conn.commit()