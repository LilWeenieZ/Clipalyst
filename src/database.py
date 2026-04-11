import sqlite3
import os
from datetime import datetime

class ClipboardDB:
    def __init__(self, db_path="./data/clipboard.db"):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clipboard_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    content_type TEXT,
                    ai_label TEXT,
                    ai_tags TEXT,
                    copied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    pinned INTEGER DEFAULT 0,
                    source_app TEXT
                )
            ''')
            
            # Create indexes on copied_at and content
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_copied_at ON clipboard_items(copied_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_content ON clipboard_items(content)')
            conn.commit()

    def insert_item(self, content, source_app=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO clipboard_items (content, source_app)
                VALUES (?, ?)
            ''', (content, source_app))
            conn.commit()
            return cursor.lastrowid

    def get_item_content(self, item_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content FROM clipboard_items WHERE id = ?', (item_id,))
            row = cursor.fetchone()
            return row['content'] if row else None

    def update_ai_tags(self, item_id, content_type, ai_label):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE clipboard_items
                SET content_type = ?, ai_label = ?
                WHERE id = ?
            ''', (content_type, ai_label, item_id))
            conn.commit()

    def get_recent(self, limit=200):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM clipboard_items
                ORDER BY copied_at DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def search(self, query, tags=None, limit=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            
            # Base query
            sql = '''
                SELECT * FROM clipboard_items 
                WHERE (content LIKE ? OR ai_label LIKE ? OR ai_tags LIKE ? OR source_app LIKE ?)
            '''
            params = [search_pattern, search_pattern, search_pattern, search_pattern]
            
            # Add tag filtering if tags are provided
            if tags:
                placeholders = ', '.join(['?' for _ in tags])
                sql += f" AND LOWER(content_type) IN ({placeholders})"
                params.extend([t.lower() for t in tags])
            
            sql += " ORDER BY pinned DESC, copied_at DESC"
            
            if limit:
                sql += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def pin_item(self, item_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE clipboard_items
                SET pinned = 1
                WHERE id = ?
            ''', (item_id,))
            conn.commit()

    def unpin_item(self, item_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE clipboard_items
                SET pinned = 0
                WHERE id = ?
            ''', (item_id,))
            conn.commit()

    def delete_item(self, item_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM clipboard_items
                WHERE id = ?
            ''', (item_id,))
            conn.commit()

    def clear_all(self) -> int:
        """Delete all non-pinned clipboard items. Returns the number of rows removed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clipboard_items WHERE pinned = 0")
            conn.commit()
            return cursor.rowcount

    def delete_older_than(self, days):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Deletes older items but keeps pinned ones
            modifier = f"-{int(days)} days"
            cursor.execute('''
                DELETE FROM clipboard_items
                WHERE copied_at < datetime('now', ?) AND pinned = 0
            ''', (modifier,))
            conn.commit()
            return cursor.rowcount

    def enforce_limit(self, limit):
        """Keep only the N most recent non-pinned items (plus all pinned items).

        Compares by integer ``id`` rather than timestamp so that items sharing
        the same ``copied_at`` value are never over-deleted.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Find the id of the (limit)-th most recent non-pinned item.
            cursor.execute('''
                SELECT id FROM clipboard_items
                WHERE pinned = 0
                ORDER BY copied_at DESC, id DESC
                LIMIT 1 OFFSET ?
            ''', (limit - 1,))
            row = cursor.fetchone()
            if row:
                cutoff_id = row['id']
                # Delete every non-pinned item whose id is strictly less than
                # cutoff_id (older rows always have lower auto-increment ids).
                cursor.execute('''
                    DELETE FROM clipboard_items
                    WHERE id < ? AND pinned = 0
                ''', (cutoff_id,))
                conn.commit()
                return cursor.rowcount
        return 0

    def get_stats(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) as total FROM clipboard_items')
            total = cursor.fetchone()['total']
            
            cursor.execute('SELECT COUNT(*) as pinned FROM clipboard_items WHERE pinned = 1')
            pinned = cursor.fetchone()['pinned']
            
            return {
                "total_items": total,
                "pinned_items": pinned
            }


if __name__ == "__main__":
    db = ClipboardDB()
    print("--- Testing ClipboardDB ---")
    print("Database initialized successfully at ./data/clipboard.db")

    print("\nInserting a test item...")
    item_id = db.insert_item("https://github.com/google/gemini", "Google Chrome")
    print(f"Inserted item with ID: {item_id}")

    print("\nRecent items:")
    for item in db.get_recent(5):
        print(f" - [{item['id']}] {item['content']} (Source: {item['source_app']}) - Pinned: {item['pinned']}")

    print("\nPinning the test item...")
    db.pin_item(item_id)

    print("Getting stats...")
    stats = db.get_stats()
    print(f"Stats: {stats}")

    print("\nSearching for 'github'...")
    results = db.search("github")
    print(f"Found {len(results)} items matching 'github':")
    for r in results:
        print(f" - [{r['id']}] {r['content']}")

    print("\n--- Test Complete ---")
