"""
Object Storage Utilities - Handle persistent file storage using Replit Object Storage
"""
import os
import logging
from io import BytesIO

try:
    from replit.object_storage import Client
    OBJECT_STORAGE_AVAILABLE = True
except ImportError:
    OBJECT_STORAGE_AVAILABLE = False
    logging.warning("Replit Object Storage not available, falling back to local storage")


def get_storage_client():
    """Get the Object Storage client"""
    if not OBJECT_STORAGE_AVAILABLE:
        return None
    try:
        return Client()
    except Exception as e:
        logging.error(f"Failed to initialize Object Storage client: {e}")
        return None


def upload_file(file_data, object_path):
    """
    Upload a file to Object Storage
    
    Args:
        file_data: File bytes or file-like object
        object_path: Path in object storage (e.g., 'uploads/images/filename.jpg')
    
    Returns:
        bool: True if successful, False otherwise
    """
    client = get_storage_client()
    
    if client:
        try:
            if hasattr(file_data, 'read'):
                data = file_data.read()
                file_data.seek(0)
            else:
                data = file_data
            
            client.upload_from_bytes(object_path, data)
            logging.info(f"Uploaded to Object Storage: {object_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to upload to Object Storage: {e}")
            return False
    
    return False


def download_file(object_path):
    """
    Download a file from Object Storage
    
    Args:
        object_path: Path in object storage
    
    Returns:
        bytes: File content or None if not found
    """
    client = get_storage_client()
    
    if client:
        try:
            data = client.download_as_bytes(object_path)
            return data
        except Exception as e:
            logging.debug(f"Object not found in storage: {object_path}")
            return None
    
    return None


def delete_file(object_path):
    """
    Delete a file from Object Storage
    
    Args:
        object_path: Path in object storage
    
    Returns:
        bool: True if successful, False otherwise
    """
    client = get_storage_client()
    
    if client:
        try:
            client.delete(object_path)
            logging.info(f"Deleted from Object Storage: {object_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to delete from Object Storage: {e}")
            return False
    
    return False


def file_exists(object_path):
    """
    Check if a file exists in Object Storage
    
    Args:
        object_path: Path in object storage
    
    Returns:
        bool: True if exists, False otherwise
    """
    client = get_storage_client()
    
    if client:
        try:
            objects = client.list()
            return object_path in [obj.name for obj in objects]
        except Exception as e:
            logging.error(f"Failed to check file existence: {e}")
            return False
    
    return False


def list_files(prefix=''):
    """
    List files in Object Storage with given prefix
    
    Args:
        prefix: Path prefix to filter by
    
    Returns:
        list: List of file paths
    """
    client = get_storage_client()
    
    if client:
        try:
            objects = client.list()
            if prefix:
                return [obj.name for obj in objects if obj.name.startswith(prefix)]
            return [obj.name for obj in objects]
        except Exception as e:
            logging.error(f"Failed to list files: {e}")
            return []
    
    return []
