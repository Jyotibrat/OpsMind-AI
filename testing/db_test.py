from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

uri = os.getenv("MONGODB_URI")

client = MongoClient(uri)

try:
    client.admin.command("ping")
    print("Connected to MongoDB Atlas successfully!")
except Exception as e:
    print("Connection failed:", e)