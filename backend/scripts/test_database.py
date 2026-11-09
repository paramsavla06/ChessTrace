"""
Legacy alias for backend/scripts/seed_database.py.
Delegates execution to seed_database.py for backward compatibility.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_database import insert_test_data, verify_database

if __name__ == "__main__":
    print("[INFO] test_database.py is an alias for seed_database.py. Running seed...")
    insert_test_data()
    verify_database()
