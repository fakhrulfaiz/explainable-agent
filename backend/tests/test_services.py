"""
Unit tests for service classes using repository pattern
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.services.chat_history_service import ChatHistoryService
from src.services.checkpoint_service import CheckpointService
from src.repositories.checkpoint_repository import CheckpointWriteEntry, CheckpointEntry
from src.models.chat_models import ChatThread, ChatMessage, ChatThreadSummary


class TestChatHistoryService:
    """Test cases for ChatHistoryService with repository pattern"""
    
    @pytest.mark.asyncio
    async def test_create_thread_success(self, chat_history_service, mock_chat_thread_repo, sample_create_request):
        """Test successful thread creation"""
        # Mock repository to return success
        mock_chat_thread_repo.create_thread.return_value = True
        
        # Call the service method
        result = await chat_history_service.create_thread(sample_create_request)
        
        # Assertions
        assert result is not None
        assert result.title == "Test Chat"
        assert len(result.messages) == 1
        assert result.messages[0].content == "Hello, world!"
        
        # Verify repository was called
        mock_chat_thread_repo.create_thread.assert_called_once()
        call_args = mock_chat_thread_repo.create_thread.call_args[0][0]
        assert isinstance(call_args, ChatThread)
        assert call_args.title == "Test Chat"
    
    @pytest.mark.asyncio
    async def test_create_thread_repository_failure(self, chat_history_service, mock_chat_thread_repo, sample_create_request):
        """Test thread creation when repository fails"""
        # Mock repository to return failure
        mock_chat_thread_repo.create_thread.return_value = False
        
        # Call the service method and expect exception
        with pytest.raises(Exception) as exc_info:
            await chat_history_service.create_thread(sample_create_request)
        
        assert "Failed to create chat thread in database" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_thread_found(self, chat_history_service, mock_chat_thread_repo, sample_chat_thread):
        """Test getting an existing thread"""
        # Mock repository to return thread
        mock_chat_thread_repo.find_by_thread_id.return_value = sample_chat_thread
        
        # Call the service method
        result = await chat_history_service.get_thread("test-thread-123")
        
        # Assertions
        assert result is not None
        assert result.thread_id == "test-thread-123"
        assert result.title == "Test Chat"
        
        # Verify repository was called
        mock_chat_thread_repo.find_by_thread_id.assert_called_once_with("test-thread-123")
    
    @pytest.mark.asyncio
    async def test_get_thread_not_found(self, chat_history_service, mock_chat_thread_repo):
        """Test getting a non-existent thread"""
        # Mock repository to return None
        mock_chat_thread_repo.find_by_thread_id.return_value = None
        
        # Call the service method
        result = await chat_history_service.get_thread("non-existent")
        
        # Assertions
        assert result is None
        mock_chat_thread_repo.find_by_thread_id.assert_called_once_with("non-existent")
    
    @pytest.mark.asyncio
    async def test_add_message_success(self, chat_history_service, mock_chat_thread_repo, sample_add_message_request):
        """Test successfully adding a message"""
        # Mock repository to return success
        mock_chat_thread_repo.add_message_to_thread.return_value = True
        
        # Call the service method
        result = await chat_history_service.add_message(sample_add_message_request)
        
        # Assertions
        assert result is True
        
        # Verify repository was called with correct parameters
        mock_chat_thread_repo.add_message_to_thread.assert_called_once()
        call_args = mock_chat_thread_repo.add_message_to_thread.call_args
        assert call_args[0][0] == "test-thread-123"  # thread_id
        assert isinstance(call_args[0][1], ChatMessage)  # message
        assert call_args[0][1].content == "Hello! How can I help you?"
    
    @pytest.mark.asyncio
    async def test_add_message_thread_not_found(self, chat_history_service, mock_chat_thread_repo, sample_add_message_request):
        """Test adding a message to non-existent thread"""
        # Mock repository to return failure
        mock_chat_thread_repo.add_message_to_thread.return_value = False
        
        # Call the service method
        result = await chat_history_service.add_message(sample_add_message_request)
        
        # Assertions
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_thread_success(self, chat_history_service, mock_chat_thread_repo, mock_checkpoint_service):
        """Test successful thread deletion with checkpoint cleanup"""
        # Mock repository and checkpoint service
        mock_chat_thread_repo.delete_thread.return_value = True
        mock_checkpoint_service.delete_all_thread_data.return_value = {"total_deleted": 5}
        
        # Call the service method
        result = await chat_history_service.delete_thread("test-thread")
        
        # Assertions
        assert result is True
        
        # Verify both repository and checkpoint service were called
        mock_chat_thread_repo.delete_thread.assert_called_once_with("test-thread")
        mock_checkpoint_service.delete_all_thread_data.assert_called_once_with("test-thread")
    
    @pytest.mark.asyncio
    async def test_delete_thread_not_found(self, chat_history_service, mock_chat_thread_repo, mock_checkpoint_service):
        """Test deleting a non-existent thread"""
        # Mock repository to return failure
        mock_chat_thread_repo.delete_thread.return_value = False
        
        # Call the service method
        result = await chat_history_service.delete_thread("non-existent")
        
        # Assertions
        assert result is False
        
        # Verify repository was called but checkpoint service wasn't
        mock_chat_thread_repo.delete_thread.assert_called_once_with("non-existent")
        mock_checkpoint_service.delete_all_thread_data.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_delete_thread_checkpoint_cleanup_fails(self, chat_history_service, mock_chat_thread_repo, mock_checkpoint_service):
        """Test thread deletion when checkpoint cleanup fails"""
        # Mock repository success but checkpoint service failure
        mock_chat_thread_repo.delete_thread.return_value = True
        mock_checkpoint_service.delete_all_thread_data.side_effect = Exception("Checkpoint error")
        
        # Call the service method - should still succeed despite checkpoint failure
        result = await chat_history_service.delete_thread("test-thread")
        
        # Assertions - operation should still succeed
        assert result is True
        
        # Verify both were called
        mock_chat_thread_repo.delete_thread.assert_called_once_with("test-thread")
        mock_checkpoint_service.delete_all_thread_data.assert_called_once_with("test-thread")
    
    @pytest.mark.asyncio
    async def test_update_thread_title_success(self, chat_history_service, mock_chat_thread_repo):
        """Test successful thread title update"""
        # Mock repository to return success
        mock_chat_thread_repo.update_thread_title.return_value = True
        
        # Call the service method
        result = await chat_history_service.update_thread_title("test-thread", "New Title")
        
        # Assertions
        assert result is True
        mock_chat_thread_repo.update_thread_title.assert_called_once_with("test-thread", "New Title")
    
    @pytest.mark.asyncio
    async def test_get_all_threads(self, chat_history_service, mock_chat_thread_repo):
        """Test getting all threads with pagination"""
        # Mock repository to return summaries
        mock_summaries = [
            ChatThreadSummary(
                thread_id="thread-1",
                title="Chat 1",
                last_message="Hello",
                message_count=2,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            ChatThreadSummary(
                thread_id="thread-2",
                title="Chat 2",
                last_message="Hi there",
                message_count=1,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        ]
        mock_chat_thread_repo.get_thread_summaries.return_value = mock_summaries
        
        # Call the service method
        result = await chat_history_service.get_all_threads(limit=10, skip=0)
        
        # Assertions
        assert len(result) == 2
        assert result[0].thread_id == "thread-1"
        assert result[1].thread_id == "thread-2"
        mock_chat_thread_repo.get_thread_summaries.assert_called_once_with(limit=10, skip=0)
    
    @pytest.mark.asyncio
    async def test_get_thread_count(self, chat_history_service, mock_chat_thread_repo):
        """Test getting thread count"""
        # Mock repository to return count
        mock_chat_thread_repo.count_threads.return_value = 15
        
        # Call the service method
        result = await chat_history_service.get_thread_count()
        
        # Assertions
        assert result == 15
        mock_chat_thread_repo.count_threads.assert_called_once()


class TestCheckpointService:
    """Test cases for CheckpointService with repository pattern"""
    
    @pytest.mark.asyncio
    async def test_add_checkpoint_write_success(self, checkpoint_service, mock_checkpoint_write_repo):
        """Test successful checkpoint write creation"""
        # Mock repository to return success
        mock_checkpoint_write_repo.create_checkpoint_write.return_value = True
        
        # Call the service method
        result = await checkpoint_service.add_checkpoint_write(
            checkpoint_id="test-checkpoint",
            data={"key": "value"},
            thread_id="test-thread"
        )
        
        # Assertions
        assert result is True
        
        # Verify repository was called with correct parameters
        mock_checkpoint_write_repo.create_checkpoint_write.assert_called_once()
        call_args = mock_checkpoint_write_repo.create_checkpoint_write.call_args[0][0]
        assert isinstance(call_args, CheckpointWriteEntry)
        assert call_args.checkpoint_id == "test-checkpoint"
        assert call_args.data == {"key": "value"}
        assert call_args.thread_id == "test-thread"
    
    @pytest.mark.asyncio
    async def test_add_checkpoint_success(self, checkpoint_service, mock_checkpoint_repo):
        """Test successful checkpoint creation"""
        # Mock repository to return success
        mock_checkpoint_repo.create_checkpoint.return_value = True
        
        # Call the service method
        result = await checkpoint_service.add_checkpoint(
            checkpoint_id="test-checkpoint",
            checkpoint_data={"state": "test"},
            thread_id="test-thread"
        )
        
        # Assertions
        assert result is True
        
        # Verify repository was called with correct parameters
        mock_checkpoint_repo.create_checkpoint.assert_called_once()
        call_args = mock_checkpoint_repo.create_checkpoint.call_args[0][0]
        assert isinstance(call_args, CheckpointEntry)
        assert call_args.checkpoint_id == "test-checkpoint"
        assert call_args.checkpoint_data == {"state": "test"}
        assert call_args.thread_id == "test-thread"
    
    @pytest.mark.asyncio
    async def test_delete_checkpoint_writes_by_thread(self, checkpoint_service, mock_checkpoint_write_repo):
        """Test deleting checkpoint writes by thread ID"""
        # Mock repository to return deletion count
        mock_checkpoint_write_repo.delete_by_thread_id.return_value = 3
        
        # Call the service method
        result = await checkpoint_service.delete_checkpoint_writes_by_thread("test-thread")
        
        # Assertions
        assert result == 3
        mock_checkpoint_write_repo.delete_by_thread_id.assert_called_once_with("test-thread")
    
    @pytest.mark.asyncio
    async def test_delete_checkpoints_by_thread(self, checkpoint_service, mock_checkpoint_repo):
        """Test deleting checkpoints by thread ID"""
        # Mock repository to return deletion count
        mock_checkpoint_repo.delete_by_thread_id.return_value = 2
        
        # Call the service method
        result = await checkpoint_service.delete_checkpoints_by_thread("test-thread")
        
        # Assertions
        assert result == 2
        mock_checkpoint_repo.delete_by_thread_id.assert_called_once_with("test-thread")
    
    @pytest.mark.asyncio
    async def test_get_checkpoint_found(self, checkpoint_service, mock_checkpoint_repo):
        """Test getting an existing checkpoint"""
        # Mock repository to return checkpoint entry
        mock_entry = CheckpointEntry(
            checkpoint_id="test-checkpoint",
            checkpoint_data={"state": "test"},
            thread_id="test-thread"
        )
        mock_checkpoint_repo.find_by_checkpoint_id.return_value = mock_entry
        
        # Call the service method
        result = await checkpoint_service.get_checkpoint("test-checkpoint")
        
        # Assertions
        assert result is not None
        assert result["checkpoint_id"] == "test-checkpoint"
        assert result["checkpoint_data"] == {"state": "test"}
        mock_checkpoint_repo.find_by_checkpoint_id.assert_called_once_with("test-checkpoint")
    
    @pytest.mark.asyncio
    async def test_get_checkpoint_not_found(self, checkpoint_service, mock_checkpoint_repo):
        """Test getting a non-existent checkpoint"""
        # Mock repository to return None
        mock_checkpoint_repo.find_by_checkpoint_id.return_value = None
        
        # Call the service method
        result = await checkpoint_service.get_checkpoint("non-existent")
        
        # Assertions
        assert result is None
        mock_checkpoint_repo.find_by_checkpoint_id.assert_called_once_with("non-existent")
    
    @pytest.mark.asyncio
    async def test_delete_all_checkpoint_data(self, checkpoint_service, mock_checkpoint_write_repo, mock_checkpoint_repo):
        """Test deleting all checkpoint data for a checkpoint ID"""
        # Mock the internal method calls
        checkpoint_service.delete_checkpoint_write = AsyncMock(return_value=True)
        checkpoint_service.delete_checkpoint = AsyncMock(return_value=True)
        
        # Call the service method
        result = await checkpoint_service.delete_all_checkpoint_data("test-checkpoint")
        
        # Assertions
        assert result["checkpoint_writes_deleted"] is True
        assert result["checkpoint_deleted"] is True
        
        # Verify internal methods were called
        checkpoint_service.delete_checkpoint_write.assert_called_once_with("test-checkpoint")
        checkpoint_service.delete_checkpoint.assert_called_once_with("test-checkpoint")
    
    @pytest.mark.asyncio
    async def test_get_checkpoint_count(self, checkpoint_service, mock_checkpoint_repo):
        """Test getting checkpoint count"""
        # Mock repository to return count
        mock_checkpoint_repo.count.return_value = 10
        
        # Call the service method
        result = await checkpoint_service.get_checkpoint_count()
        
        # Assertions
        assert result == 10
        mock_checkpoint_repo.count.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_checkpoint_writes_count(self, checkpoint_service, mock_checkpoint_write_repo):
        """Test getting checkpoint writes count"""
        # Mock repository to return count
        mock_checkpoint_write_repo.count.return_value = 25
        
        # Call the service method
        result = await checkpoint_service.get_checkpoint_writes_count()
        
        # Assertions
        assert result == 25
        mock_checkpoint_write_repo.count.assert_called_once()


class TestServiceErrorHandling:
    """Test error handling in services"""
    
    @pytest.mark.asyncio
    async def test_create_thread_repository_exception(self, chat_history_service, mock_chat_thread_repo, sample_create_request):
        """Test handling repository exceptions during thread creation"""
        # Mock repository to raise exception
        mock_chat_thread_repo.create_thread.side_effect = Exception("Repository error")
        
        # Call the service method and expect exception
        with pytest.raises(Exception) as exc_info:
            await chat_history_service.create_thread(sample_create_request)
        
        assert "Failed to create chat thread" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_thread_repository_exception(self, chat_history_service, mock_chat_thread_repo):
        """Test handling repository exceptions during thread retrieval"""
        # Mock repository to raise exception
        mock_chat_thread_repo.find_by_thread_id.side_effect = Exception("Repository error")
        
        # Call the service method and expect exception
        with pytest.raises(Exception) as exc_info:
            await chat_history_service.get_thread("test-thread")
        
        assert "Failed to retrieve chat thread" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_checkpoint_service_error_returns_zero_count(self, checkpoint_service, mock_checkpoint_repo):
        """Test that checkpoint count returns 0 on error"""
        # Mock repository to raise exception
        mock_checkpoint_repo.count.side_effect = Exception("Repository error")
        
        # Call the service method
        result = await checkpoint_service.get_checkpoint_count()
        
        # Should return 0 instead of raising exception
        assert result == 0
