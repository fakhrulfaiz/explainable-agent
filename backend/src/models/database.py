from typing import Generator
from pymongo import MongoClient
from pymongo.database import Database
from langgraph.checkpoint.mongodb import MongoDBSaver
from .config import settings


class MongoDBManager:
    """Manages MongoDB connections with proper lifecycle management"""
    
    def __init__(self):
        self._client: MongoClient | None = None
        self._db: Database | None = None
        self._mongo_memory: MongoDBSaver | None = None
    
    def get_mongo_uri(self) -> str:
        """Generate MongoDB connection URI from settings"""
        return f"mongodb://{settings.mongo_username}:{settings.mongo_password}@{settings.mongo_host}:{settings.mongo_port}/{settings.mongo_database}?authSource={settings.mongo_auth_source}"
    
    def connect(self) -> None:
        """Establish MongoDB connection"""
        if self._client is None:
            try:
                uri = self.get_mongo_uri()
                self._client = MongoClient(
                    uri,
                    maxPoolSize=10,  # Connection pool size
                    minPoolSize=1,    # Minimum connections to maintain
                    maxIdleTimeMS=30000,  # Close idle connections after 30s
                    serverSelectionTimeoutMS=5000,  # 5s timeout for server selection
                    connectTimeoutMS=10000,  # 10s timeout for connection
                )
                # Test the connection
                self._client.admin.command('ping')
                self._db = self._client.get_database()
                self._mongo_memory = MongoDBSaver(self._db)
                print("✅ MongoDB connected successfully")
            except Exception as e:
                print(f"❌ MongoDB connection failed: {e}")
                raise
    
    def get_database(self) -> Database:
        """Get database instance, connecting if necessary"""
        if self._db is None:
            self.connect()
        return self._db
    
    def get_mongo_memory(self) -> MongoDBSaver:
        """Get MongoDBSaver instance, connecting if necessary"""
        if self._mongo_memory is None:
            self.connect()
        return self._mongo_memory
    
    def close(self) -> None:
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._mongo_memory = None
            print("🔌 MongoDB connection closed")


# Global instance
mongodb_manager = MongoDBManager()


# Dependency functions for FastAPI
def get_mongodb() -> Generator[Database, None, None]:
    """FastAPI dependency for MongoDB database"""
    try:
        db = mongodb_manager.get_database()
        yield db
    except Exception as e:
        print(f"❌ MongoDB dependency error: {e}")
        raise
    # Note: We don't close here as the manager handles connection pooling


def get_mongo_memory() -> Generator[MongoDBSaver, None, None]:
    """FastAPI dependency for MongoDBSaver"""
    try:
        mongo_memory = mongodb_manager.get_mongo_memory()
        yield mongo_memory
    except Exception as e:
        print(f"❌ MongoDBSaver dependency error: {e}")
        raise


# Legacy access for backward compatibility (deprecated)
def get_mongo_uri() -> str:
    """Legacy function - use dependency injection instead"""
    return mongodb_manager.get_mongo_uri()


# These will be removed in favor of dependency injection
mongo_uri = get_mongo_uri()
mongo_client = mongodb_manager._client
db = mongodb_manager._db
mongo_memory = mongodb_manager._mongo_memory
