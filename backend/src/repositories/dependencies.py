from fastapi import Depends
from pymongo.database import Database

from src.models.database import get_mongodb
from .chat_thread_repository import ChatThreadRepository
from .checkpoint_repository import CheckpointWriteRepository, CheckpointRepository
from src.services.chat_history_service import ChatHistoryService
from src.services.checkpoint_service import CheckpointService
from src.repositories.messages_repository import MessagesRepository

# Repository Dependencies
def get_chat_thread_repository(db: Database = Depends(get_mongodb)) -> ChatThreadRepository:
    """Dependency to get ChatThreadRepository"""
    return ChatThreadRepository(db)

def get_checkpoint_write_repository(db: Database = Depends(get_mongodb)) -> CheckpointWriteRepository:
    """Dependency to get CheckpointWriteRepository"""
    return CheckpointWriteRepository(db)

def get_checkpoint_repository(db: Database = Depends(get_mongodb)) -> CheckpointRepository:
    """Dependency to get CheckpointRepository"""
    return CheckpointRepository(db)

def get_messages_repository(db: Database = Depends(get_mongodb)) -> MessagesRepository:
    """Dependency to get MessagesRepository"""
    return MessagesRepository(db)


# Service Dependencies (using repositories)
def get_checkpoint_service(
    checkpoint_write_repo: CheckpointWriteRepository = Depends(get_checkpoint_write_repository),
    checkpoint_repo: CheckpointRepository = Depends(get_checkpoint_repository)
):
    return CheckpointService(checkpoint_write_repo, checkpoint_repo)

def get_chat_history_service(
    chat_thread_repo: ChatThreadRepository = Depends(get_chat_thread_repository),
    checkpoint_service = Depends(get_checkpoint_service),
    messages_repo: MessagesRepository = Depends(get_messages_repository)
):
    return ChatHistoryService(chat_thread_repo, checkpoint_service, messages_repo)

