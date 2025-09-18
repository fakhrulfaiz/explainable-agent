"""
Test configuration and fixtures for repository pattern tests
"""
import pytest
from unittest.mock import Mock, AsyncMock
from pymongo.database import Database
from pymongo.collection import Collection
from datetime import datetime

from src.repositories.chat_thread_repository import ChatThreadRepository
from src.repositories.checkpoint_repository import CheckpointWriteRepository, CheckpointRepository
from src.services.chat_history_service import ChatHistoryService
from src.services.checkpoint_service import CheckpointService
from src.models.chat_models import ChatThread, ChatMessage, CreateChatRequest, AddMessageRequest


@pytest.fixture
def mock_database():
    """Mock MongoDB database"""
    db = Mock(spec=Database)
    return db


@pytest.fixture
def mock_collection():
    """Mock MongoDB collection"""
    collection = Mock(spec=Collection)
    return collection


@pytest.fixture
def mock_chat_thread_repo():
    """Mock ChatThreadRepository"""
    repo = Mock(spec=ChatThreadRepository)
    # Make methods async
    repo.create_thread = AsyncMock()
    repo.find_by_thread_id = AsyncMock()
    repo.add_message_to_thread = AsyncMock()
    repo.update_thread_title = AsyncMock()
    repo.delete_thread = AsyncMock()
    repo.get_thread_summaries = AsyncMock()
    repo.count_threads = AsyncMock()
    return repo


@pytest.fixture
def mock_checkpoint_write_repo():
    """Mock CheckpointWriteRepository"""
    repo = Mock(spec=CheckpointWriteRepository)
    repo.create_checkpoint_write = AsyncMock()
    repo.delete_by_thread_id = AsyncMock()
    repo.delete_by_checkpoint_id = AsyncMock()
    repo.delete_by_object_id = AsyncMock()
    repo.find_by_checkpoint_id = AsyncMock()
    repo.count = AsyncMock()
    return repo


@pytest.fixture
def mock_checkpoint_repo():
    """Mock CheckpointRepository"""
    repo = Mock(spec=CheckpointRepository)
    repo.create_checkpoint = AsyncMock()
    repo.delete_by_thread_id = AsyncMock()
    repo.delete_by_checkpoint_id = AsyncMock()
    repo.find_by_checkpoint_id = AsyncMock()
    repo.get_all_checkpoints = AsyncMock()
    repo.count = AsyncMock()
    return repo


@pytest.fixture
def mock_checkpoint_service():
    """Mock CheckpointService"""
    service = Mock(spec=CheckpointService)
    service.delete_all_thread_data = AsyncMock()
    return service


@pytest.fixture
def sample_chat_thread():
    """Sample ChatThread for testing"""
    return ChatThread(
        thread_id="test-thread-123",
        title="Test Chat",
        messages=[
            ChatMessage(
                sender="user",
                content="Hello, world!",
                timestamp=datetime.now()
            )
        ],
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def sample_create_request():
    """Sample CreateChatRequest for testing"""
    return CreateChatRequest(
        title="Test Chat",
        initial_message="Hello, world!"
    )


@pytest.fixture
def sample_add_message_request():
    """Sample AddMessageRequest for testing"""
    return AddMessageRequest(
        thread_id="test-thread-123",
        sender="assistant",
        content="Hello! How can I help you?",
        message_type="message"
    )


@pytest.fixture
def chat_history_service(mock_chat_thread_repo, mock_checkpoint_service):
    """ChatHistoryService with mocked dependencies"""
    return ChatHistoryService(mock_chat_thread_repo, mock_checkpoint_service)


@pytest.fixture
def checkpoint_service(mock_checkpoint_write_repo, mock_checkpoint_repo):
    """CheckpointService with mocked dependencies"""
    return CheckpointService(mock_checkpoint_write_repo, mock_checkpoint_repo)
