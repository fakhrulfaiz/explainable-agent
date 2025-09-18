"""
Unit tests for repository classes
"""
import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime
from pymongo.errors import PyMongoError

from src.repositories.chat_thread_repository import ChatThreadRepository
from src.repositories.checkpoint_repository import CheckpointWriteRepository, CheckpointRepository, CheckpointWriteEntry, CheckpointEntry
from src.models.chat_models import ChatThread, ChatMessage, ChatThreadSummary


class TestChatThreadRepository:
    """Test cases for ChatThreadRepository"""
    
    @pytest.fixture
    def chat_thread_repo(self, mock_database):
        """Create ChatThreadRepository with mocked database"""
        with patch.object(ChatThreadRepository, '_create_indexes'):
            return ChatThreadRepository(mock_database)
    
    @pytest.mark.asyncio
    async def test_create_thread_success(self, chat_thread_repo, sample_chat_thread):
        """Test successful thread creation"""
        # Mock the collection.insert_one to return a successful result
        mock_result = Mock()
        mock_result.inserted_id = "mock_id"
        chat_thread_repo.collection.insert_one.return_value = mock_result
        
        # Call the method
        result = await chat_thread_repo.create_thread(sample_chat_thread)
        
        # Assertions
        assert result is True
        chat_thread_repo.collection.insert_one.assert_called_once()
        call_args = chat_thread_repo.collection.insert_one.call_args[0][0]
        assert call_args['thread_id'] == sample_chat_thread.thread_id
        assert call_args['title'] == sample_chat_thread.title
    
    @pytest.mark.asyncio
    async def test_find_by_thread_id_found(self, chat_thread_repo, sample_chat_thread):
        """Test finding an existing thread"""
        # Mock the collection.find_one to return thread data
        thread_data = sample_chat_thread.dict()
        chat_thread_repo.collection.find_one.return_value = thread_data
        
        # Call the method
        result = await chat_thread_repo.find_by_thread_id("test-thread-123")
        
        # Assertions
        assert result is not None
        assert result.thread_id == "test-thread-123"
        assert result.title == "Test Chat"
        chat_thread_repo.collection.find_one.assert_called_once_with({"thread_id": "test-thread-123"})
    
    @pytest.mark.asyncio
    async def test_find_by_thread_id_not_found(self, chat_thread_repo):
        """Test finding a non-existent thread"""
        # Mock the collection.find_one to return None
        chat_thread_repo.collection.find_one.return_value = None
        
        # Call the method
        result = await chat_thread_repo.find_by_thread_id("non-existent")
        
        # Assertions
        assert result is None
        chat_thread_repo.collection.find_one.assert_called_once_with({"thread_id": "non-existent"})
    
    @pytest.mark.asyncio
    async def test_add_message_to_thread_success(self, chat_thread_repo):
        """Test successfully adding a message to a thread"""
        # Mock successful update
        mock_result = Mock()
        mock_result.modified_count = 1
        chat_thread_repo.collection.update_one.return_value = mock_result
        
        message = ChatMessage(
            sender="user",
            content="Test message",
            timestamp=datetime.now()
        )
        
        # Call the method
        result = await chat_thread_repo.add_message_to_thread("test-thread", message)
        
        # Assertions
        assert result is True
        chat_thread_repo.collection.update_one.assert_called_once()
        call_args = chat_thread_repo.collection.update_one.call_args
        assert call_args[0][0] == {"thread_id": "test-thread"}
        assert "$push" in call_args[0][1]
        assert "$set" in call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_add_message_to_thread_not_found(self, chat_thread_repo):
        """Test adding a message to a non-existent thread"""
        # Mock no modification
        mock_result = Mock()
        mock_result.modified_count = 0
        chat_thread_repo.collection.update_one.return_value = mock_result
        
        message = ChatMessage(
            sender="user",
            content="Test message",
            timestamp=datetime.now()
        )
        
        # Call the method
        result = await chat_thread_repo.add_message_to_thread("non-existent", message)
        
        # Assertions
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_thread_success(self, chat_thread_repo):
        """Test successful thread deletion"""
        # Mock successful deletion
        mock_result = Mock()
        mock_result.deleted_count = 1
        chat_thread_repo.collection.delete_one.return_value = mock_result
        
        # Call the method
        result = await chat_thread_repo.delete_thread("test-thread")
        
        # Assertions
        assert result is True
        chat_thread_repo.collection.delete_one.assert_called_once_with({"thread_id": "test-thread"})
    
    @pytest.mark.asyncio
    async def test_count_threads(self, chat_thread_repo):
        """Test counting threads"""
        # Mock count result
        chat_thread_repo.collection.count_documents.return_value = 5
        
        # Call the method
        result = await chat_thread_repo.count_threads()
        
        # Assertions
        assert result == 5
        chat_thread_repo.collection.count_documents.assert_called_once_with({})


class TestCheckpointWriteRepository:
    """Test cases for CheckpointWriteRepository"""
    
    @pytest.fixture
    def checkpoint_write_repo(self, mock_database):
        """Create CheckpointWriteRepository with mocked database"""
        with patch.object(CheckpointWriteRepository, '_create_indexes'):
            return CheckpointWriteRepository(mock_database)
    
    @pytest.mark.asyncio
    async def test_create_checkpoint_write_success(self, checkpoint_write_repo):
        """Test successful checkpoint write creation"""
        # Mock successful insertion
        mock_result = Mock()
        mock_result.inserted_id = "mock_id"
        checkpoint_write_repo.collection.insert_one.return_value = mock_result
        
        entry = CheckpointWriteEntry(
            checkpoint_id="test-checkpoint",
            data={"key": "value"},
            thread_id="test-thread"
        )
        
        # Call the method
        result = await checkpoint_write_repo.create_checkpoint_write(entry)
        
        # Assertions
        assert result is True
        checkpoint_write_repo.collection.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_by_thread_id(self, checkpoint_write_repo):
        """Test deleting checkpoint writes by thread ID"""
        # Mock deletion result
        mock_result = Mock()
        mock_result.deleted_count = 3
        checkpoint_write_repo.collection.delete_many.return_value = mock_result
        
        # Call the method
        result = await checkpoint_write_repo.delete_by_thread_id("test-thread")
        
        # Assertions
        assert result == 3
        checkpoint_write_repo.collection.delete_many.assert_called_once_with({"thread_id": "test-thread"})
    
    @pytest.mark.asyncio
    async def test_delete_by_checkpoint_id(self, checkpoint_write_repo):
        """Test deleting checkpoint writes by checkpoint ID"""
        # Mock deletion result
        mock_result = Mock()
        mock_result.deleted_count = 2
        checkpoint_write_repo.collection.delete_many.return_value = mock_result
        
        # Call the method
        result = await checkpoint_write_repo.delete_by_checkpoint_id("test-checkpoint")
        
        # Assertions
        assert result == 2
        checkpoint_write_repo.collection.delete_many.assert_called_once_with({"checkpoint_id": "test-checkpoint"})


class TestCheckpointRepository:
    """Test cases for CheckpointRepository"""
    
    @pytest.fixture
    def checkpoint_repo(self, mock_database):
        """Create CheckpointRepository with mocked database"""
        with patch.object(CheckpointRepository, '_create_indexes'):
            return CheckpointRepository(mock_database)
    
    @pytest.mark.asyncio
    async def test_create_checkpoint_success(self, checkpoint_repo):
        """Test successful checkpoint creation"""
        # Mock successful insertion
        mock_result = Mock()
        mock_result.inserted_id = "mock_id"
        checkpoint_repo.collection.insert_one.return_value = mock_result
        
        entry = CheckpointEntry(
            checkpoint_id="test-checkpoint",
            checkpoint_data={"state": "test"},
            thread_id="test-thread"
        )
        
        # Call the method
        result = await checkpoint_repo.create_checkpoint(entry)
        
        # Assertions
        assert result is True
        checkpoint_repo.collection.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_by_checkpoint_id_found(self, checkpoint_repo):
        """Test finding an existing checkpoint"""
        # Mock the collection.find_one to return checkpoint data
        checkpoint_data = {
            "checkpoint_id": "test-checkpoint",
            "checkpoint_data": {"state": "test"},
            "thread_id": "test-thread",
            "created_at": datetime.now()
        }
        checkpoint_repo.collection.find_one.return_value = checkpoint_data
        
        # Call the method
        result = await checkpoint_repo.find_by_checkpoint_id("test-checkpoint")
        
        # Assertions
        assert result is not None
        assert result.checkpoint_id == "test-checkpoint"
        checkpoint_repo.collection.find_one.assert_called_once_with({"checkpoint_id": "test-checkpoint"})
    
    @pytest.mark.asyncio
    async def test_find_by_checkpoint_id_not_found(self, checkpoint_repo):
        """Test finding a non-existent checkpoint"""
        # Mock the collection.find_one to return None
        checkpoint_repo.collection.find_one.return_value = None
        
        # Call the method
        result = await checkpoint_repo.find_by_checkpoint_id("non-existent")
        
        # Assertions
        assert result is None
        checkpoint_repo.collection.find_one.assert_called_once_with({"checkpoint_id": "non-existent"})
    
    @pytest.mark.asyncio
    async def test_delete_by_thread_id(self, checkpoint_repo):
        """Test deleting checkpoints by thread ID"""
        # Mock deletion result
        mock_result = Mock()
        mock_result.deleted_count = 2
        checkpoint_repo.collection.delete_many.return_value = mock_result
        
        # Call the method
        result = await checkpoint_repo.delete_by_thread_id("test-thread")
        
        # Assertions
        assert result == 2
        checkpoint_repo.collection.delete_many.assert_called_once_with({"thread_id": "test-thread"})


class TestErrorHandling:
    """Test error handling in repositories"""
    
    @pytest.fixture
    def chat_thread_repo(self, mock_database):
        """Create ChatThreadRepository with mocked database"""
        with patch.object(ChatThreadRepository, '_create_indexes'):
            return ChatThreadRepository(mock_database)
    
    @pytest.mark.asyncio
    async def test_create_thread_database_error(self, chat_thread_repo, sample_chat_thread):
        """Test handling database errors during thread creation"""
        # Mock PyMongoError
        chat_thread_repo.collection.insert_one.side_effect = PyMongoError("Database error")
        
        # Call the method and expect exception
        with pytest.raises(Exception) as exc_info:
            await chat_thread_repo.create_thread(sample_chat_thread)
        
        assert "Failed to create document" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_find_by_thread_id_database_error(self, chat_thread_repo):
        """Test handling database errors during thread retrieval"""
        # Mock PyMongoError
        chat_thread_repo.collection.find_one.side_effect = PyMongoError("Database error")
        
        # Call the method and expect exception
        with pytest.raises(Exception) as exc_info:
            await chat_thread_repo.find_by_thread_id("test-thread")
        
        assert "Failed to find document" in str(exc_info.value)
