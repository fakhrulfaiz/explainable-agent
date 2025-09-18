from typing import Generator
from pymongo import AsyncMongoClient, MongoClient
from pymongo.database import Database
from langgraph.checkpoint.mongodb import MongoDBSaver
from .config import settings


class MongoDBManager:
    
    def __init__(self):
        self._async_client: AsyncMongoClient | None = None
        self._sync_client: MongoClient | None = None
        self._db: Database | None = None
        self._mongo_memory: MongoDBSaver | None = None
    
    def get_mongo_uri(self) -> str:
        return f"mongodb://{settings.mongo_username}:{settings.mongo_password}@{settings.mongo_host}:{settings.mongo_port}/{settings.mongo_database}?authSource={settings.mongo_auth_source}"
    
    def connect(self) -> None:
        if self._async_client is None or self._sync_client is None:
            try:
                uri = self.get_mongo_uri()
                
                # Create async client for repositories
                self._async_client = AsyncMongoClient(
                    uri,
                    maxPoolSize=10,  # Connection pool size
                    minPoolSize=1,    # Minimum connections to maintain
                    maxIdleTimeMS=30000,  # Close idle connections after 30s
                    serverSelectionTimeoutMS=5000,  # 5s timeout for server selection
                    connectTimeoutMS=10000,  # 10s timeout for connection
                )
                
                # Create sync client for MongoDBSaver (LangGraph requirement)
                self._sync_client = MongoClient(
                    uri,
                    maxPoolSize=10,
                    minPoolSize=1,
                    maxIdleTimeMS=30000,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                )
                
                # Test the sync connection (MongoDBSaver needs this to work)
                self._sync_client.admin.command('ping')
                
                # Use async client for database operations
                self._db = self._async_client.get_database()
                
                # Use sync client for MongoDBSaver
                sync_db = self._sync_client.get_database()
                self._mongo_memory = MongoDBSaver(sync_db)
                
                print("✅ MongoDB connected successfully (both async and sync)")
            except Exception as e:
                print(f"❌ MongoDB connection failed: {e}")
                raise
    
    def get_database(self) -> Database:
        if self._db is None:
            self.connect()
        return self._db
    
    def get_mongo_memory(self) -> MongoDBSaver:
        if self._mongo_memory is None:
            self.connect()
        return self._mongo_memory
    
    def close(self) -> None:
        """Close MongoDB connections"""
        if self._async_client:
            self._async_client.close()
            self._async_client = None
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None
        self._db = None
        self._mongo_memory = None
        print("🔌 MongoDB connections closed")


# Global instance
mongodb_manager = MongoDBManager()


# Dependency functions for FastAPI
def get_mongodb() -> Generator[Database, None, None]:
    try:
        db = mongodb_manager.get_database()
        yield db
    except Exception as e:
        print(f"❌ MongoDB dependency error: {e}")
        raise


def get_mongo_memory() -> Generator[MongoDBSaver, None, None]:
    """FastAPI dependency for MongoDBSaver"""
    try:
        mongo_memory = mongodb_manager.get_mongo_memory()
        yield mongo_memory
    except Exception as e:
        print(f"❌ MongoDBSaver dependency error: {e}")
        raise


def get_mongo_uri() -> str:
    """Legacy function - use dependency injection instead"""
    return mongodb_manager.get_mongo_uri()


# These will be removed in favor of dependency injection
mongo_uri = get_mongo_uri()
mongo_client = mongodb_manager._async_client
db = mongodb_manager._db
mongo_memory = mongodb_manager._mongo_memory