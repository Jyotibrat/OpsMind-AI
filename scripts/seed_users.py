"""
scripts/seed_users.py
─────────────────────
One-time script to create the default admin and employee users in MongoDB.
Run this ONCE after setting up your .env:

    python scripts/seed_users.py

Uses the same bare MongoClient approach as create_vector_index.py.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import bcrypt
from pymongo import MongoClient
from app.config import settings


def seed_users() -> None:
    print(f"Connecting to MongoDB Atlas: {settings.MONGODB_URI[:40]}…")
    client = MongoClient(settings.MONGODB_URI)

    # Verify connection
    client.admin.command("ping")
    print("✓ Connected to MongoDB Atlas")

    db = client[settings.DB_NAME]
    users_col = db["users"]

    defaults = [
        {
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD,
            "role": "admin",
            "display_name": "Administrator",
        },
        {
            "username": settings.EMPLOYEE_USERNAME,
            "password": settings.EMPLOYEE_PASSWORD,
            "role": "employee",
            "display_name": "Employee",
        },
    ]

    for u in defaults:
        existing = users_col.find_one({"username": u["username"]})
        if existing:
            print(f"  ↳ User '{u['username']}' already exists — skipping.")
        else:
            hashed = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
            users_col.insert_one(
                {
                    "username": u["username"],
                    "hashed_password": hashed,
                    "role": u["role"],
                    "display_name": u["display_name"],
                }
            )
            print(f"  ✓ Created {u['role']} user: '{u['username']}'")

    client.close()
    print("\n✓ User seeding complete! You can now log in at http://localhost:8000/app/")


if __name__ == "__main__":
    seed_users()
