#!/usr/bin/env python3
"""Migration script to add background fields to User table."""

import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from server.settings import get_settings


def migrate_database(db_path):
    """Add light_bg_id and dark_bg_id columns to users table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'light_bg_id' not in columns:
        print(f"Adding light_bg_id column to {db_path}...")
        cursor.execute("ALTER TABLE users ADD COLUMN light_bg_id VARCHAR(64)")
    else:
        print(f"light_bg_id already exists in {db_path}")
    
    if 'dark_bg_id' not in columns:
        print(f"Adding dark_bg_id column to {db_path}...")
        cursor.execute("ALTER TABLE users ADD COLUMN dark_bg_id VARCHAR(64)")
    else:
        print(f"dark_bg_id already exists in {db_path}")
    
    conn.commit()
    conn.close()
    print(f"Migration completed for {db_path}")


def main():
    settings = get_settings()
    db_url = settings.database_url
    
    if db_url.startswith('sqlite://'):
        db_path_str = db_url.replace('sqlite:///', '').replace('sqlite://', '')
        if db_path_str.startswith('./'):
            db_path_str = db_path_str[2:]
        db_path = project_root / db_path_str
        
        if db_path.exists():
            migrate_database(str(db_path))
        else:
            print(f"Database not found at {db_path}")
            print("It will be created automatically when the server starts.")
    else:
        print("Non-SQLite database detected. Please run migrations manually.")


if __name__ == '__main__':
    main()
