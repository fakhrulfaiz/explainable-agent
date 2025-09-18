"""
Integration tests for repository pattern implementation
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.repositories.chat_thread_repository import ChatThreadRepository
from src.repositories.checkpoint_repository import CheckpointWriteRepository, CheckpointRepository
from src.services.chat_history_service import ChatHistoryService
from src.services.checkpoint_service import CheckpointService
from src.models.chat_models import CreateChatRequest, AddMessageRequest


class TestChatHistoryIntegration:
    """Integration tests for ChatHistoryService with real repository interactions"""
    
    @pytest.fixture
    def mock_database(self):
        """Mock database for integration tests"""
        return Mock()
    
    @pytest.fixture
    def chat_history_service_integration(self, mock_database):
        """ChatHistoryService with real repositories but mocked database"""
        # Create real repositories with mocked database
        with patch.object(ChatThreadRepository, '_create_indexes'), \
             patch.object(CheckpointWriteRepository, '_create_indexes'), \
             patch.object(CheckpointRepository, '_create_indexes'):
            
            chat_thread_repo = ChatThreadRepository(mock_database)
            checkpoint_write_repo = CheckpointWriteRepository(mock_database)
            checkpoint_repo = CheckpointRepository(mock_database)
            
            # Create real services with real repositories
            checkpoint_service = CheckpointService(checkpoint_write_repo, checkpoint_repo)
            chat_history_service = ChatHistoryService(chat_thread_repo, checkpoint_service)
            
            return chat_history_service, chat_thread_repo, checkpoint_service
    
    @pytest.mark.asyncio
    async def test_full_chat_thread_lifecycle(self, chat_history_service_integration):
        """Test complete chat thread lifecycle through service and repository layers"""
        service, repo, checkpoint_service = chat_history_service_integration
        
        # Mock database responses for the full lifecycle
        
        # 1. Create thread
        mock_insert_result = Mock()
        mock_insert_result.inserted_id = "mock_id"
        repo.collection.insert_one.return_value = mock_insert_result
        
        create_request = CreateChatRequest(
            title="Integration Test Chat",
            initial_message="Hello from integration test!"
        )
        
        # Call create
        thread = await service.create_thread(create_request)
        
        # Verify thread creation
        assert thread is not None
        assert thread.title == "Integration Test Chat"
        assert len(thread.messages) == 1
        assert thread.messages[0].content == "Hello from integration test!"
        
        # Verify repository was called
        repo.collection.insert_one.assert_called_once()
        
        # 2. Add message to thread
        mock_update_result = Mock()
        mock_update_result.modified_count = 1
        repo.collection.update_one.return_value = mock_update_result
        
        add_message_request = AddMessageRequest(
            thread_id=thread.thread_id,
            sender="assistant",
            content="Hello! How can I help you today?",
            message_type="message"
        )
        
        # Call add message
        message_added = await service.add_message(add_message_request)
        
        # Verify message addition
        assert message_added is True
        repo.collection.update_one.assert_called_once()
        
        # 3. Get thread
        thread_data = thread.dict()
        thread_data['messages'].append({
            "sender": "assistant",
            "content": "Hello! How can I help you today?",
            "timestamp": datetime.now(),
            "message_type": "message",
            "checkpoint_id": None
        })
        repo.collection.find_one.return_value = thread_data
        
        # Call get thread
        retrieved_thread = await service.get_thread(thread.thread_id)
        
        # Verify thread retrieval
        assert retrieved_thread is not None
        assert retrieved_thread.thread_id == thread.thread_id
        assert retrieved_thread.title == "Integration Test Chat"
        
        # 4. Update thread title
        mock_update_title_result = Mock()
        mock_update_title_result.modified_count = 1
        repo.collection.update_one.return_value = mock_update_title_result
        
        # Call update title
        title_updated = await service.update_thread_title(thread.thread_id, "Updated Integration Test Chat")
        
        # Verify title update
        assert title_updated is True
        
        # 5. Delete thread
        mock_delete_result = Mock()
        mock_delete_result.deleted_count = 1
        repo.collection.delete_one.return_value = mock_delete_result
        
        # Mock checkpoint service cleanup
        checkpoint_service.delete_all_thread_data = Mock()
        checkpoint_service.delete_all_thread_data.return_value = {"total_deleted": 0}
        
        # Call delete thread
        thread_deleted = await service.delete_thread(thread.thread_id)
        
        # Verify thread deletion
        assert thread_deleted is True
        repo.collection.delete_one.assert_called_once()
        checkpoint_service.delete_all_thread_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_thread_with_checkpoint_integration(self, chat_history_service_integration):
        """Test chat thread with checkpoint operations"""
        service, repo, checkpoint_service = chat_history_service_integration
        
        # Mock thread creation
        mock_insert_result = Mock()
        mock_insert_result.inserted_id = "thread_id"
        repo.collection.insert_one.return_value = mock_insert_result
        
        create_request = CreateChatRequest(
            title="Checkpoint Test Chat",
            initial_message="Test with checkpoints"
        )
        
        # Create thread
        thread = await service.create_thread(create_request)
        
        # Mock checkpoint operations
        checkpoint_service.checkpoint_write_repo.create_checkpoint_write = Mock()
        checkpoint_service.checkpoint_write_repo.create_checkpoint_write.return_value = True
        
        checkpoint_service.checkpoint_repo.create_checkpoint = Mock()
        checkpoint_service.checkpoint_repo.create_checkpoint.return_value = True
        
        # Add checkpoint write
        checkpoint_write_success = await checkpoint_service.add_checkpoint_write(
            checkpoint_id="test-checkpoint-1",
            data={"step": 1, "action": "query"},
            thread_id=thread.thread_id
        )
        
        # Add checkpoint
        checkpoint_success = await checkpoint_service.add_checkpoint(
            checkpoint_id="test-checkpoint-1",
            checkpoint_data={"state": "completed"},
            thread_id=thread.thread_id
        )
        
        # Verify checkpoint operations
        assert checkpoint_write_success is True
        assert checkpoint_success is True
        
        # Mock cleanup operations
        checkpoint_service.checkpoint_write_repo.delete_by_thread_id = Mock()
        checkpoint_service.checkpoint_write_repo.delete_by_thread_id.return_value = 1
        
        checkpoint_service.checkpoint_repo.delete_by_thread_id = Mock()
        checkpoint_service.checkpoint_repo.delete_by_thread_id.return_value = 1
        
        # Test cleanup when deleting thread
        cleanup_result = await checkpoint_service.delete_all_thread_data(thread.thread_id)
        
        # Verify cleanup
        assert cleanup_result["checkpoint_writes_deleted"] == 1
        assert cleanup_result["checkpoints_deleted"] == 1


class TestErrorPropagation:
    """Test error propagation through the repository pattern layers"""
    
    @pytest.fixture
    def service_with_failing_repo(self, mock_database):
        """Service with repository that will fail"""
        with patch.object(ChatThreadRepository, '_create_indexes'):
            repo = ChatThreadRepository(mock_database)
            checkpoint_service = Mock()
            service = ChatHistoryService(repo, checkpoint_service)
            return service, repo
    
    @pytest.mark.asyncio
    async def test_database_error_propagation(self, service_with_failing_repo):
        """Test that database errors propagate correctly through all layers"""
        service, repo = service_with_failing_repo
        
        # Make repository fail with database error
        from pymongo.errors import PyMongoError
        repo.collection.insert_one.side_effect = PyMongoError("Connection failed")
        
        create_request = CreateChatRequest(
            title="Failing Test",
            initial_message="This will fail"
        )
        
        # Service should catch repository error and re-raise with context
        with pytest.raises(Exception) as exc_info:
            await service.create_thread(create_request)
        
        # Verify error message contains service context
        assert "Failed to create chat thread" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_service_resilience_to_checkpoint_failures(self, chat_history_service_integration):
        """Test that main operations continue even if checkpoint operations fail"""
        service, repo, checkpoint_service = chat_history_service_integration
        
        # Mock successful thread deletion
        mock_delete_result = Mock()
        mock_delete_result.deleted_count = 1
        repo.collection.delete_one.return_value = mock_delete_result
        
        # Mock checkpoint service to fail
        checkpoint_service.delete_all_thread_data = Mock()
        checkpoint_service.delete_all_thread_data.side_effect = Exception("Checkpoint cleanup failed")
        
        # Thread deletion should still succeed despite checkpoint failure
        result = await service.delete_thread("test-thread")
        
        # Verify main operation succeeded
        assert result is True
        
        # Verify both operations were attempted
        repo.collection.delete_one.assert_called_once()
        checkpoint_service.delete_all_thread_data.assert_called_once()


class TestDependencyInjection:
    """Test dependency injection patterns"""
    
    def test_service_dependencies(self):
        """Test that services receive correct dependencies"""
        # Mock dependencies
        chat_thread_repo = Mock()
        checkpoint_service = Mock()
        
        # Create service
        service = ChatHistoryService(chat_thread_repo, checkpoint_service)
        
        # Verify dependencies are stored correctly
        assert service.chat_thread_repo is chat_thread_repo
        assert service.checkpoint_service is checkpoint_service
    
    def test_checkpoint_service_dependencies(self):
        """Test that checkpoint service receives correct dependencies"""
        # Mock dependencies
        checkpoint_write_repo = Mock()
        checkpoint_repo = Mock()
        
        # Create service
        service = CheckpointService(checkpoint_write_repo, checkpoint_repo)
        
        # Verify dependencies are stored correctly
        assert service.checkpoint_write_repo is checkpoint_write_repo
        assert service.checkpoint_repo is checkpoint_repo
    
    def test_repository_dependencies(self, mock_database):
        """Test that repositories receive correct dependencies"""
        with patch.object(ChatThreadRepository, '_create_indexes'):
            repo = ChatThreadRepository(mock_database)
            
            # Verify database dependency
            assert repo.db is mock_database
            assert repo.collection is not None
