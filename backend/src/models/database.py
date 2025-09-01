from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver
from .config import settings


# MongoDB connection
def get_mongo_uri() -> str:
    return f"mongodb://{settings.mongo_username}:{settings.mongo_password}@{settings.mongo_host}:{settings.mongo_port}/{settings.mongo_database}?authSource={settings.mongo_auth_source}"


# MongoDB client and database
mongo_uri = get_mongo_uri()
mongo_client = MongoClient(mongo_uri)
db = mongo_client.get_database()

# Create MongoDB checkpoint for LangGraph
mongo_memory = MongoDBSaver(db)
