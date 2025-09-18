#!/usr/bin/env python3
"""
Migration script to clean up user data and use only MongoDB _id
"""
import asyncio
from pymongo import MongoClient
from bson import ObjectId
from src.models.config import settings

async def migrate_users():
    """Remove redundant user_id field and use only MongoDB _id"""
    
    # Connect to MongoDB
    client = MongoClient(
        f"mongodb://{settings.mongo_username}:{settings.mongo_password}@{settings.mongo_host}:{settings.mongo_port}/{settings.mongo_database}?authSource={settings.mongo_auth_source}"
    )
    db = client.get_database()
    
    print("🔄 Starting user migration...")
    
    # Step 1: Remove user_id field from all user documents
    print("📝 Removing redundant user_id field...")
    result = db.users.update_many(
        {},  # All documents
        {"$unset": {"user_id": ""}}  # Remove user_id field
    )
    print(f"✅ Updated {result.modified_count} user documents")
    
    # Step 2: Update any references in other collections
    print("🔗 Updating references in other collections...")
    
    # Update chat threads if they reference user_id
    chat_result = db.chat_threads.update_many(
        {"user_id": {"$exists": True}},
        {"$unset": {"user_id": ""}}
    )
    print(f"✅ Updated {chat_result.modified_count} chat thread documents")
    
    # Update checkpoints if they reference user_id
    checkpoint_result = db["checkpointing_db.checkpoints"].update_many(
        {"user_id": {"$exists": True}},
        {"$unset": {"user_id": ""}}
    )
    print(f"✅ Updated {checkpoint_result.modified_count} checkpoint documents")
    
    checkpoint_writes_result = db["checkpointing_db.checkpoint_writes"].update_many(
        {"user_id": {"$exists": True}},
        {"$unset": {"user_id": ""}}
    )
    print(f"✅ Updated {checkpoint_writes_result.modified_count} checkpoint write documents")
    
    # Step 3: Drop the old user_id index
    print("🗑️ Dropping old user_id index...")
    try:
        db.users.drop_index("user_id_1")
        print("✅ Dropped user_id index")
    except Exception as e:
        print(f"ℹ️ user_id index not found or already dropped: {e}")
    
    print("🎉 Migration completed successfully!")
    print("\n📊 Summary:")
    print(f"   - Users updated: {result.modified_count}")
    print(f"   - Chat threads updated: {chat_result.modified_count}")
    print(f"   - Checkpoints updated: {checkpoint_result.modified_count}")
    print(f"   - Checkpoint writes updated: {checkpoint_writes_result.modified_count}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate_users())
