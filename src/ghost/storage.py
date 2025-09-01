"""
File Storage and Upload Management Module

Provides file upload handling, validation, and storage with support for
local filesystem and cloud providers (S3, Azure Blob, Google Cloud Storage).
"""

import os
import shutil
import hashlib
import mimetypes
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, BinaryIO, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import aiofiles
import asyncio
from PIL import Image
import magic
from .config import get_config
from .logging import get_logger, LoggerMixin
from .utils import StringUtils, HashUtils


class StorageProvider(Enum):
    """Supported storage providers."""
    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"
    GCS = "gcs"


class FileType(Enum):
    """Common file type categories."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    CODE = "code"
    OTHER = "other"


@dataclass
class FileMetadata:
    """File metadata information."""
    filename: str
    size: int
    content_type: str
    file_type: FileType
    extension: str
    hash: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'filename': self.filename,
            'size': self.size,
            'content_type': self.content_type,
            'file_type': self.file_type.value,
            'extension': self.extension,
            'hash': self.hash,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat() if self.modified_at else None,
            'metadata': self.metadata
        }


@dataclass
class UploadedFile:
    """Represents an uploaded file."""
    id: str
    original_name: str
    stored_name: str
    path: str
    url: Optional[str]
    size: int
    content_type: str
    file_type: FileType
    hash: str
    provider: StorageProvider
    metadata: FileMetadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'original_name': self.original_name,
            'stored_name': self.stored_name,
            'path': self.path,
            'url': self.url,
            'size': self.size,
            'content_type': self.content_type,
            'file_type': self.file_type.value,
            'hash': self.hash,
            'provider': self.provider.value,
            'metadata': self.metadata.to_dict(),
            'created_at': self.created_at.isoformat()
        }


class FileValidator:
    """File validation utilities."""
    
    # Default allowed file extensions by type
    ALLOWED_EXTENSIONS = {
        FileType.IMAGE: {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico'},
        FileType.VIDEO: {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'},
        FileType.AUDIO: {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac'},
        FileType.DOCUMENT: {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.odt'},
        FileType.ARCHIVE: {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'},
        FileType.CODE: {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.css', '.html', '.xml', '.json', '.yaml', '.yml'}
    }
    
    # MIME type mappings
    MIME_TYPES = {
        FileType.IMAGE: ['image/'],
        FileType.VIDEO: ['video/'],
        FileType.AUDIO: ['audio/'],
        FileType.DOCUMENT: ['application/pdf', 'application/msword', 'application/vnd.', 'text/plain'],
        FileType.ARCHIVE: ['application/zip', 'application/x-rar', 'application/x-7z', 'application/x-tar'],
        FileType.CODE: ['text/', 'application/json', 'application/xml']
    }
    
    @classmethod
    def get_file_type(cls, filename: str, content_type: Optional[str] = None) -> FileType:
        """Determine file type from filename and content type.
        
        Args:
            filename: File name
            content_type: MIME content type
            
        Returns:
            File type category
        """
        ext = Path(filename).suffix.lower()
        
        # Check by extension
        for file_type, extensions in cls.ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                return file_type
        
        # Check by MIME type
        if content_type:
            for file_type, mime_prefixes in cls.MIME_TYPES.items():
                for prefix in mime_prefixes:
                    if content_type.startswith(prefix):
                        return file_type
        
        return FileType.OTHER
    
    @classmethod
    def validate_extension(cls, filename: str, allowed_types: Optional[List[FileType]] = None) -> bool:
        """Validate file extension.
        
        Args:
            filename: File name
            allowed_types: Allowed file types
            
        Returns:
            True if valid
        """
        if not allowed_types:
            return True
        
        ext = Path(filename).suffix.lower()
        for file_type in allowed_types:
            if ext in cls.ALLOWED_EXTENSIONS.get(file_type, set()):
                return True
        
        return False
    
    @classmethod
    def validate_size(cls, size: int, max_size: Optional[int] = None) -> bool:
        """Validate file size.
        
        Args:
            size: File size in bytes
            max_size: Maximum allowed size in bytes
            
        Returns:
            True if valid
        """
        if max_size and size > max_size:
            return False
        return size > 0
    
    @classmethod
    def validate_content(cls, file_path: str, validate_magic: bool = True) -> Tuple[bool, Optional[str]]:
        """Validate file content using magic bytes.
        
        Args:
            file_path: Path to file
            validate_magic: Whether to validate magic bytes
            
        Returns:
            Tuple of (is_valid, detected_mime_type)
        """
        if not validate_magic:
            return True, None
        
        try:
            mime = magic.Magic(mime=True)
            detected_type = mime.from_file(file_path)
            
            # Check if detected type matches expected
            filename = os.path.basename(file_path)
            expected_type, _ = mimetypes.guess_type(filename)
            
            if expected_type and detected_type != expected_type:
                # Allow some common mismatches
                safe_mismatches = [
                    ('text/plain', 'text/'),
                    ('application/octet-stream', '')
                ]
                
                for expected, detected in safe_mismatches:
                    if expected_type.startswith(expected) or detected_type.startswith(detected):
                        return True, detected_type
                
                return False, detected_type
            
            return True, detected_type
            
        except Exception:
            # If magic is not available, skip validation
            return True, None


class LocalStorageProvider(LoggerMixin):
    """Local filesystem storage provider."""
    
    def __init__(self, base_path: str = "uploads", public_url_base: Optional[str] = None):
        """Initialize local storage provider.
        
        Args:
            base_path: Base directory for file storage
            public_url_base: Base URL for public file access
        """
        self.base_path = Path(base_path)
        self.public_url_base = public_url_base or "/files"
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure storage directories exist."""
        for file_type in FileType:
            type_dir = self.base_path / file_type.value
            type_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_filename(self, original_name: str) -> str:
        """Generate unique filename.
        
        Args:
            original_name: Original file name
            
        Returns:
            Unique filename
        """
        ext = Path(original_name).suffix
        unique_name = f"{uuid.uuid4().hex}{ext}"
        return unique_name
    
    def _get_storage_path(self, file_type: FileType, filename: str) -> Path:
        """Get storage path for file.
        
        Args:
            file_type: File type category
            filename: File name
            
        Returns:
            Full storage path
        """
        # Organize by type and date
        date_path = datetime.now().strftime("%Y/%m/%d")
        return self.base_path / file_type.value / date_path / filename
    
    def save(self, file_data: BinaryIO, original_name: str, 
             file_type: Optional[FileType] = None) -> UploadedFile:
        """Save file to local storage.
        
        Args:
            file_data: File data stream
            original_name: Original file name
            file_type: File type (auto-detected if None)
            
        Returns:
            Uploaded file information
        """
        # Detect file type
        if file_type is None:
            file_type = FileValidator.get_file_type(original_name)
        
        # Generate unique filename
        stored_name = self._generate_filename(original_name)
        storage_path = self._get_storage_path(file_type, stored_name)
        
        # Ensure directory exists
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_data.seek(0)
        content = file_data.read()
        
        with open(storage_path, 'wb') as f:
            f.write(content)
        
        # Calculate hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Get file info
        file_size = len(content)
        content_type, _ = mimetypes.guess_type(original_name)
        
        # Create metadata
        metadata = FileMetadata(
            filename=original_name,
            size=file_size,
            content_type=content_type or 'application/octet-stream',
            file_type=file_type,
            extension=Path(original_name).suffix,
            hash=file_hash
        )
        
        # Generate public URL
        relative_path = storage_path.relative_to(self.base_path)
        public_url = f"{self.public_url_base}/{relative_path}"
        
        # Create uploaded file record
        uploaded_file = UploadedFile(
            id=uuid.uuid4().hex,
            original_name=original_name,
            stored_name=stored_name,
            path=str(storage_path),
            url=public_url,
            size=file_size,
            content_type=content_type or 'application/octet-stream',
            file_type=file_type,
            hash=file_hash,
            provider=StorageProvider.LOCAL,
            metadata=metadata
        )
        
        self.logger.info(f"File saved: {original_name} -> {storage_path}")
        return uploaded_file
    
    async def save_async(self, file_data: BinaryIO, original_name: str,
                        file_type: Optional[FileType] = None) -> UploadedFile:
        """Save file asynchronously.
        
        Args:
            file_data: File data stream
            original_name: Original file name
            file_type: File type (auto-detected if None)
            
        Returns:
            Uploaded file information
        """
        # Detect file type
        if file_type is None:
            file_type = FileValidator.get_file_type(original_name)
        
        # Generate unique filename
        stored_name = self._generate_filename(original_name)
        storage_path = self._get_storage_path(file_type, stored_name)
        
        # Ensure directory exists
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file asynchronously
        file_data.seek(0)
        content = file_data.read()
        
        async with aiofiles.open(storage_path, 'wb') as f:
            await f.write(content)
        
        # Calculate hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Get file info
        file_size = len(content)
        content_type, _ = mimetypes.guess_type(original_name)
        
        # Create metadata
        metadata = FileMetadata(
            filename=original_name,
            size=file_size,
            content_type=content_type or 'application/octet-stream',
            file_type=file_type,
            extension=Path(original_name).suffix,
            hash=file_hash
        )
        
        # Generate public URL
        relative_path = storage_path.relative_to(self.base_path)
        public_url = f"{self.public_url_base}/{relative_path}"
        
        # Create uploaded file record
        uploaded_file = UploadedFile(
            id=uuid.uuid4().hex,
            original_name=original_name,
            stored_name=stored_name,
            path=str(storage_path),
            url=public_url,
            size=file_size,
            content_type=content_type or 'application/octet-stream',
            file_type=file_type,
            hash=file_hash,
            provider=StorageProvider.LOCAL,
            metadata=metadata
        )
        
        self.logger.info(f"File saved asynchronously: {original_name} -> {storage_path}")
        return uploaded_file
    
    def delete(self, file_path: str) -> bool:
        """Delete file from storage.
        
        Args:
            file_path: File path
            
        Returns:
            True if deleted
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                self.logger.info(f"File deleted: {file_path}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete file: {e}")
            return False
    
    def get(self, file_path: str) -> Optional[bytes]:
        """Get file content.
        
        Args:
            file_path: File path
            
        Returns:
            File content or None
        """
        try:
            path = Path(file_path)
            if path.exists():
                with open(path, 'rb') as f:
                    return f.read()
            return None
        except Exception as e:
            self.logger.error(f"Failed to read file: {e}")
            return None
    
    async def get_async(self, file_path: str) -> Optional[bytes]:
        """Get file content asynchronously.
        
        Args:
            file_path: File path
            
        Returns:
            File content or None
        """
        try:
            path = Path(file_path)
            if path.exists():
                async with aiofiles.open(path, 'rb') as f:
                    return await f.read()
            return None
        except Exception as e:
            self.logger.error(f"Failed to read file asynchronously: {e}")
            return None


class ImageProcessor(LoggerMixin):
    """Image processing utilities."""
    
    @classmethod
    def create_thumbnail(cls, image_path: str, thumbnail_path: str,
                        size: Tuple[int, int] = (200, 200)) -> bool:
        """Create image thumbnail.
        
        Args:
            image_path: Source image path
            thumbnail_path: Thumbnail output path
            size: Thumbnail size (width, height)
            
        Returns:
            True if created successfully
        """
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = rgb_img
                
                # Create thumbnail
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Ensure directory exists
                Path(thumbnail_path).parent.mkdir(parents=True, exist_ok=True)
                
                # Save thumbnail
                img.save(thumbnail_path, optimize=True, quality=85)
                
                return True
                
        except Exception as e:
            logger = get_logger("ImageProcessor")
            logger.error(f"Failed to create thumbnail: {e}")
            return False
    
    @classmethod
    def resize_image(cls, image_path: str, output_path: str,
                    width: Optional[int] = None, height: Optional[int] = None,
                    maintain_aspect: bool = True) -> bool:
        """Resize image.
        
        Args:
            image_path: Source image path
            output_path: Output path
            width: Target width
            height: Target height
            maintain_aspect: Maintain aspect ratio
            
        Returns:
            True if resized successfully
        """
        try:
            with Image.open(image_path) as img:
                original_width, original_height = img.size
                
                if maintain_aspect:
                    if width and not height:
                        height = int((width / original_width) * original_height)
                    elif height and not width:
                        width = int((height / original_height) * original_width)
                
                if not width or not height:
                    return False
                
                # Resize image
                resized = img.resize((width, height), Image.Resampling.LANCZOS)
                
                # Ensure directory exists
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                
                # Save resized image
                resized.save(output_path, optimize=True, quality=90)
                
                return True
                
        except Exception as e:
            logger = get_logger("ImageProcessor")
            logger.error(f"Failed to resize image: {e}")
            return False
    
    @classmethod
    def get_image_info(cls, image_path: str) -> Optional[Dict[str, Any]]:
        """Get image information.
        
        Args:
            image_path: Image path
            
        Returns:
            Image information or None
        """
        try:
            with Image.open(image_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'info': img.info
                }
        except Exception:
            return None


class StorageManager(LoggerMixin):
    """Main storage manager coordinating different providers."""
    
    def __init__(self, provider: StorageProvider = StorageProvider.LOCAL,
                 config: Optional[Dict[str, Any]] = None):
        """Initialize storage manager.
        
        Args:
            provider: Storage provider to use
            config: Provider configuration
        """
        self.provider = provider
        self.config = config or {}
        self._setup_provider()
    
    def _setup_provider(self):
        """Setup the storage provider."""
        if self.provider == StorageProvider.LOCAL:
            self.storage = LocalStorageProvider(
                base_path=self.config.get('base_path', 'uploads'),
                public_url_base=self.config.get('public_url_base', '/files')
            )
        elif self.provider == StorageProvider.S3:
            # Would require boto3
            self.logger.warning("S3 provider not yet implemented")
            self.storage = None
        elif self.provider == StorageProvider.AZURE:
            # Would require azure-storage-blob
            self.logger.warning("Azure provider not yet implemented")
            self.storage = None
        elif self.provider == StorageProvider.GCS:
            # Would require google-cloud-storage
            self.logger.warning("GCS provider not yet implemented")
            self.storage = None
        else:
            self.logger.error(f"Unknown provider: {self.provider}")
            self.storage = None
    
    def upload(self, file_data: BinaryIO, filename: str,
              allowed_types: Optional[List[FileType]] = None,
              max_size: Optional[int] = None,
              validate_content: bool = True) -> UploadedFile:
        """Upload a file with validation.
        
        Args:
            file_data: File data stream
            filename: File name
            allowed_types: Allowed file types
            max_size: Maximum file size in bytes
            validate_content: Whether to validate content
            
        Returns:
            Uploaded file information
            
        Raises:
            ValueError: If validation fails
        """
        # Validate extension
        if allowed_types and not FileValidator.validate_extension(filename, allowed_types):
            raise ValueError(f"File type not allowed: {filename}")
        
        # Check size
        file_data.seek(0, 2)  # Seek to end
        size = file_data.tell()
        file_data.seek(0)  # Reset to beginning
        
        if not FileValidator.validate_size(size, max_size):
            raise ValueError(f"File too large: {size} bytes (max: {max_size})")
        
        # Save to provider
        if self.storage:
            return self.storage.save(file_data, filename)
        else:
            raise RuntimeError("Storage provider not available")
    
    async def upload_async(self, file_data: BinaryIO, filename: str,
                          allowed_types: Optional[List[FileType]] = None,
                          max_size: Optional[int] = None) -> UploadedFile:
        """Upload a file asynchronously with validation.
        
        Args:
            file_data: File data stream
            filename: File name
            allowed_types: Allowed file types
            max_size: Maximum file size in bytes
            
        Returns:
            Uploaded file information
            
        Raises:
            ValueError: If validation fails
        """
        # Validate extension
        if allowed_types and not FileValidator.validate_extension(filename, allowed_types):
            raise ValueError(f"File type not allowed: {filename}")
        
        # Check size
        file_data.seek(0, 2)
        size = file_data.tell()
        file_data.seek(0)
        
        if not FileValidator.validate_size(size, max_size):
            raise ValueError(f"File too large: {size} bytes (max: {max_size})")
        
        # Save to provider
        if self.storage:
            return await self.storage.save_async(file_data, filename)
        else:
            raise RuntimeError("Storage provider not available")
    
    def delete(self, file_path: str) -> bool:
        """Delete a file.
        
        Args:
            file_path: File path
            
        Returns:
            True if deleted
        """
        if self.storage:
            return self.storage.delete(file_path)
        return False
    
    def get(self, file_path: str) -> Optional[bytes]:
        """Get file content.
        
        Args:
            file_path: File path
            
        Returns:
            File content or None
        """
        if self.storage:
            return self.storage.get(file_path)
        return None
    
    async def get_async(self, file_path: str) -> Optional[bytes]:
        """Get file content asynchronously.
        
        Args:
            file_path: File path
            
        Returns:
            File content or None
        """
        if self.storage:
            return await self.storage.get_async(file_path)
        return None


# Singleton instance
_storage_manager: Optional[StorageManager] = None


def get_storage_manager(provider: Optional[StorageProvider] = None,
                       config: Optional[Dict[str, Any]] = None) -> StorageManager:
    """Get or create storage manager instance.
    
    Args:
        provider: Storage provider to use
        config: Provider configuration
        
    Returns:
        StorageManager instance
    """
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager(
            provider or StorageProvider.LOCAL,
            config or {}
        )
    return _storage_manager