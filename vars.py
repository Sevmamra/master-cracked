import os

API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")
MONGO_URL = os.environ.get("MONGO_URL", "your_mongo_url_here")
OWNER_ID = int(os.environ.get("OWNER_ID", "8734782482"))