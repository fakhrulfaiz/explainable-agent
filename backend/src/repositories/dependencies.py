from fastapi import Depends
from pymongo.database import Database

from src.models.database import get_mongodb
from .chat_thread_repository import ChatThreadRepository
from .checkpoint_repository import CheckpointWriteRepository, CheckpointRepository
from .message_content_repository import MessageContentRepository
from src.services.chat_history_service import ChatHistoryService
from src.services.checkpoint_service import CheckpointService
from src.services.message_management_service import MessageManagementService
from src.repositories.messages_repository import MessagesRepository

# Repository Dependencies
async def get_chat_thread_repository(db: Database = Depends(get_mongodb)) -> ChatThreadRepository:
    """Dependency to get ChatThreadRepository"""
    repo = ChatThreadRepository(db)
    await repo.ensure_indexes()
    return repo

async def get_checkpoint_write_repository(db: Database = Depends(get_mongodb)) -> CheckpointWriteRepository:
    """Dependency to get CheckpointWriteRepository"""
    repo = CheckpointWriteRepository(db)
    await repo.ensure_indexes()
    return repo

async def get_checkpoint_repository(db: Database = Depends(get_mongodb)) -> CheckpointRepository:
    """Dependency to get CheckpointRepository"""
    repo = CheckpointRepository(db)
    await repo.ensure_indexes()
    return repo

async def get_messages_repository(db: Database = Depends(get_mongodb)) -> MessagesRepository:
    """Dependency to get MessagesRepository"""
    repo = MessagesRepository(db)
    await repo.ensure_indexes()
    return repo

async def get_message_content_repository(db: Database = Depends(get_mongodb)) -> MessageContentRepository:
    """Dependency to get MessageContentRepository"""
    repo = MessageContentRepository(db)
    await repo.ensure_indexes()
    return repo


# Service Dependencies (using repositories)
async def get_checkpoint_service(
    checkpoint_write_repo: CheckpointWriteRepository = Depends(get_checkpoint_write_repository),
    checkpoint_repo: CheckpointRepository = Depends(get_checkpoint_repository)
):
    return CheckpointService(checkpoint_write_repo, checkpoint_repo)

async def get_chat_history_service(
    chat_thread_repo: ChatThreadRepository = Depends(get_chat_thread_repository),
    checkpoint_service = Depends(get_checkpoint_service),
    messages_repo: MessagesRepository = Depends(get_messages_repository),
    message_content_repo: MessageContentRepository = Depends(get_message_content_repository)
):
    return ChatHistoryService(chat_thread_repo, checkpoint_service, messages_repo, message_content_repo)

async def get_message_management_service(
    messages_repo: MessagesRepository = Depends(get_messages_repository),
    chat_thread_repo: ChatThreadRepository = Depends(get_chat_thread_repository),
    message_content_repo: MessageContentRepository = Depends(get_message_content_repository)
):
    return MessageManagementService(messages_repo, chat_thread_repo, message_content_repo)

