"""
Supabase Storage Service for uploading plot images.
Handles secure file uploads with proper content-type handling and public URL generation.
"""

import os
import uuid
from datetime import datetime
from typing import Optional, BinaryIO
from supabase import create_client, Client
from src.models.config import settings
import logging

logger = logging.getLogger(__name__)

class SupabaseStorageService:
    """Service for handling plot image uploads to Supabase Storage"""
    
    def __init__(self):
        """Initialize Supabase client with configuration from settings"""
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError("Supabase URL and service role key must be configured")
        
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key
        )
        self.bucket_name = "plot-images"  # Dedicated bucket for plot images
        
        # Ensure bucket exists (this will be handled by Supabase admin)
        logger.info(f"Initialized Supabase storage service for bucket: {self.bucket_name}")
    
    def _generate_file_path(self, filename: str) -> str:
        """Generate a unique file path for the uploaded image"""
        # Extract extension
        extension = filename.split('.')[-1] if '.' in filename else 'png'
        
        # Generate unique filename with timestamp and UUID
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:8]
        
        return f"plots/{timestamp}/{unique_id}.{extension}"
    
    def upload_plot_image(
        self, 
        image_data: bytes, 
        filename: str = "plot.png",
        content_type: str = "image/png"
    ) -> str:
        """
        Upload plot image to Supabase Storage and return public URL
        
        Args:
            image_data: Binary image data
            filename: Original filename (used for extension detection)
            content_type: MIME type of the image
            
        Returns:
            Public URL of the uploaded image
            
        Raises:
            Exception: If upload fails
        """
        try:
            # Generate unique file path
            file_path = self._generate_file_path(filename)
            
            # Upload file to Supabase Storage
            # Convert image_data to bytes if it's not already
            if not isinstance(image_data, bytes):
                image_data = bytes(image_data)
            
            # Upload with proper file options
            # Note: Some Supabase client versions expect upsert as a separate kwarg
            try:
                # Try with upsert as separate parameter (newer API)
                response = self.client.storage.from_(self.bucket_name).upload(
                    file_path,
                    image_data,
                    file_options={
                        "content-type": content_type,
                        "cache-control": "3600"  # Cache for 1 hour
                    },
                    upsert=False
                )
            except TypeError:
                # Fallback: try without upsert parameter (older API)
                response = self.client.storage.from_(self.bucket_name).upload(
                    file_path,
                    image_data,
                    file_options={
                        "content-type": content_type,
                        "cache-control": "3600"  # Cache for 1 hour
                    }
                )
            
            # Check for upload errors (response might be a dict or object)
            if isinstance(response, dict) and response.get("error"):
                raise Exception(f"Upload failed: {response.get('error')}")
            elif hasattr(response, 'error') and response.error:
                raise Exception(f"Upload failed: {response.error}")
            
            # Get public URL (returns string directly)
            public_url = self.client.storage.from_(self.bucket_name).get_public_url(file_path)
            
            if not public_url or (isinstance(public_url, str) and not public_url.strip()):
                raise Exception("Failed to generate public URL")
            logger.info(f"Successfully uploaded plot image: {file_path}")
            
            return public_url
            
        except Exception as e:
            logger.error(f"Failed to upload plot image: {str(e)}")
            raise Exception(f"Image upload failed: {str(e)}")
    
    def delete_plot_image(self, file_path: str) -> bool:
        """
        Delete a plot image from Supabase Storage
        
        Args:
            file_path: Path of the file to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            response = self.client.storage.from_(self.bucket_name).remove([file_path])
            
            if response.error:
                logger.error(f"Failed to delete file {file_path}: {response.error}")
                return False
            
            logger.info(f"Successfully deleted plot image: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {str(e)}")
            return False


# Global instance
_storage_service: Optional[SupabaseStorageService] = None

def get_supabase_storage_service() -> SupabaseStorageService:
    """Get or create the global Supabase storage service instance"""
    global _storage_service
    
    if _storage_service is None:
        _storage_service = SupabaseStorageService()
    
    return _storage_service
