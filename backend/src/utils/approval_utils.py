"""
Utility functions for managing message approval flags efficiently.
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.message_management_service import MessageManagementService

logger = logging.getLogger(__name__)

async def clear_previous_approvals(thread_id: str, message_service: 'MessageManagementService'):
    """
    Clear needs_approval from previous assistant messages efficiently using targeted query.
    
    This function uses a targeted database query to only fetch messages that actually
    need approval, rather than fetching all messages and filtering in memory.
    
    Args:
        thread_id: The thread ID to clear approvals for
        message_service: The message management service instance
    """
    try:
        # Use targeted query to get only messages that need approval (status = pending)
        filter_criteria = {
            "thread_id": thread_id,
            "sender": "assistant", 
            "message_status": "pending"
        }
        
        # Get only messages that need approval (much more efficient)
        approval_messages = await message_service.messages_repo.find_many(
            filter_criteria=filter_criteria
        )
        
        # Clear approval status from previous messages by setting to approved
        for msg in approval_messages:
            await message_service.update_message_status(
                thread_id=thread_id,
                message_id=msg.message_id,
                message_status="approved"
            )
            logger.info(f"Cleared pending status from message {msg.message_id}")
            
    except Exception as e:
        logger.warning(f"Failed to clear previous approval flags: {e}")
