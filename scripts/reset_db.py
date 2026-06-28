import os
import sys

# Add root folder to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import db
from backend.database.db import engine, Base

def reset_database():
    print("[*] Resetting database...")
    import backend.database.models  # Register models with Base.metadata
    Base.metadata.drop_all(bind=engine)
    db.init_db()
    print("[OK] Database schemas reinitialized and baseline inventory seeded!")

if __name__ == "__main__":
    reset_database()
