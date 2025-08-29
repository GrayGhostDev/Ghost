"""
Utilities Module

Common utility functions and classes for backend development.
Includes data validation, formatting, encryption, and other helper functions.
"""

import hashlib
import secrets
import string
import json
import csv
import io
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, TypeVar, Generic, Callable
from pathlib import Path
from dataclasses import asdict, is_dataclass
from enum import Enum
import uuid
import re
from .logging import get_logger

T = TypeVar('T')

logger = get_logger("utils")


class DateTimeUtils:
    """Utility functions for datetime operations."""
    
    @staticmethod
    def now_utc() -> datetime:
        """Get current UTC datetime."""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def to_timestamp(dt: datetime) -> float:
        """Convert datetime to Unix timestamp."""
        return dt.timestamp()
    
    @staticmethod
    def from_timestamp(timestamp: float) -> datetime:
        """Create datetime from Unix timestamp."""
        return datetime.fromtimestamp(timestamp, timezone.utc)
    
    @staticmethod
    def format_iso(dt: datetime) -> str:
        """Format datetime as ISO string."""
        return dt.isoformat()
    
    @staticmethod
    def format_datetime(dt: datetime, format_str: str) -> str:
        """Format datetime using custom format string.
        
        Supports both Python strftime and some common formats.
        """
        # Convert common format patterns
        format_mappings = {
            'YYYY': '%Y',
            'MM': '%m',
            'DD': '%d',
            'HH': '%H',
            'mm': '%M',
            'ss': '%S'
        }
        
        python_format = format_str
        for pattern, replacement in format_mappings.items():
            python_format = python_format.replace(pattern, replacement)
            
        return dt.strftime(python_format)
    
    @staticmethod
    def parse_iso(iso_string: str) -> datetime:
        """Parse ISO datetime string."""
        return datetime.fromisoformat(iso_string)


class StringUtils:
    """Utility functions for string operations."""
    
    @staticmethod
    def generate_random_string(length: int = 32, include_special: bool = False) -> str:
        """Generate a random string."""
        chars = string.ascii_letters + string.digits
        if include_special:
            chars += "!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    @staticmethod
    def generate_slug(text: str) -> str:
        """Generate URL-friendly slug from text."""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', text.lower())
        slug = re.sub(r'\s+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')
    
    @staticmethod
    def slugify(text: str) -> str:
        """Create a URL-friendly slug from text (alias for generate_slug)."""
        return StringUtils.generate_slug(text)
    
    @staticmethod
    def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """Truncate text to maximum length."""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def clean_whitespace(text: str) -> str:
        """Clean extra whitespace from text."""
        return ' '.join(text.split())
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def mask_sensitive(text: str, show_last: int = 4, mask_char: str = "*") -> str:
        """Mask sensitive information like credit cards, emails, etc."""
        if len(text) <= show_last:
            return mask_char * len(text)
        return mask_char * (len(text) - show_last) + text[-show_last:]


class HashUtils:
    """Utility functions for hashing operations."""
    
    @staticmethod
    def md5(text: str) -> str:
        """Generate MD5 hash (for non-security purposes only)."""
        return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()  # nosec B324
    
    @staticmethod
    def sha256(text: str) -> str:
        """Generate SHA256 hash."""
        return hashlib.sha256(text.encode()).hexdigest()
    
    @staticmethod
    def sha512(text: str) -> str:
        """Generate SHA512 hash."""
        return hashlib.sha512(text.encode()).hexdigest()
    
    @staticmethod
    def generate_hash(text: str, salt: Optional[str] = None) -> str:
        """Generate secure hash with optional salt."""
        if salt is None:
            salt = secrets.token_hex(16)
        combined = f"{salt}{text}"
        return f"{salt}:{hashlib.sha256(combined.encode()).hexdigest()}"
    
    @staticmethod
    def verify_hash(text: str, hashed: str) -> bool:
        """Verify text against hash."""
        try:
            salt, hash_value = hashed.split(':', 1)
            combined = f"{salt}{text}"
            return hashlib.sha256(combined.encode()).hexdigest() == hash_value
        except ValueError:
            return False


class UUIDUtils:
    """Utility functions for UUID operations."""
    
    @staticmethod
    def generate() -> str:
        """Generate a new UUID4."""
        return str(uuid.uuid4())
    
    @staticmethod
    def is_valid(uuid_string: str) -> bool:
        """Check if string is a valid UUID."""
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def short_uuid(length: int = 8) -> str:
        """Generate short UUID-like string."""
        return str(uuid.uuid4()).replace('-', '')[:length]


class ValidationUtils:
    """Utility functions for data validation."""
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> List[str]:
        """Validate that required fields are present and not empty."""
        missing = []
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                missing.append(field)
        return missing
    
    @staticmethod
    def validate_types(data: Dict[str, Any], type_map: Dict[str, type]) -> List[str]:
        """Validate data types."""
        errors = []
        for field, expected_type in type_map.items():
            if field in data and not isinstance(data[field], expected_type):
                errors.append(f"Field '{field}' must be of type {expected_type.__name__}")
        return errors
    
    @staticmethod
    def validate_length(data: Dict[str, Any], length_map: Dict[str, tuple]) -> List[str]:
        """Validate string/list lengths."""
        errors = []
        for field, (min_len, max_len) in length_map.items():
            if field in data and data[field] is not None:
                length = len(data[field])
                if length < min_len or length > max_len:
                    errors.append(f"Field '{field}' length must be between {min_len} and {max_len}")
        return errors
    
    @staticmethod
    def is_email(email: str) -> bool:
        """Validate email address format."""
        if not email or not isinstance(email, str):
            return False
        
        # Basic email regex pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email.strip()) is not None


class SerializationUtils:
    """Utility functions for data serialization."""
    
    @staticmethod
    def to_dict(obj: Any) -> Any:
        """Convert object to dictionary or appropriate type."""
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        elif hasattr(obj, '__dict__'):
            return {k: SerializationUtils.to_dict(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: SerializationUtils.to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [SerializationUtils.to_dict(item) for item in obj]
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj
    
    @staticmethod
    def to_json(obj: Any, indent: Optional[int] = None) -> str:
        """Convert object to JSON string."""
        return json.dumps(SerializationUtils.to_dict(obj), indent=indent, default=str)
    
    @staticmethod
    def from_json(json_str: str) -> Any:
        """Parse JSON string to object."""
        return json.loads(json_str)
    
    @staticmethod
    def to_csv(data: List[Dict[str, Any]], filename: Optional[str] = None) -> str:
        """Convert list of dictionaries to CSV."""
        if not data:
            return ""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        
        csv_content = output.getvalue()
        output.close()
        
        if filename:
            with open(filename, 'w', newline='') as f:
                f.write(csv_content)
        
        return csv_content


class FileUtils:
    """Utility functions for file operations."""
    
    @staticmethod
    def ensure_directory(path: Union[str, Path]) -> Path:
        """Ensure directory exists, create if it doesn't."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def get_file_size(path: Union[str, Path]) -> int:
        """Get file size in bytes."""
        return Path(path).stat().st_size
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Get file extension."""
        return Path(filename).suffix.lower()
    
    @staticmethod
    def is_safe_filename(filename: str) -> bool:
        """Check if filename is safe (no directory traversal)."""
        # Check for dangerous patterns
        dangerous = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        return not any(danger in filename for danger in dangerous)
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to be safe."""
        # Remove or replace dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.replace('..', '_')
        return filename.strip()


class CacheUtils:
    """Utility functions for caching operations."""
    
    # Simple in-memory cache
    _cache: Dict[str, Dict[str, Any]] = {}
    
    @staticmethod
    def generate_cache_key(*args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        return HashUtils.sha256(key_string)
    
    @staticmethod
    def is_cache_expired(cached_time: datetime, ttl_seconds: int) -> bool:
        """Check if cache entry has expired."""
        return (DateTimeUtils.now_utc() - cached_time).total_seconds() > ttl_seconds
    
    @staticmethod
    def set(key: str, value: Any, ttl: int = 3600) -> None:
        """Set a cache value with TTL."""
        expire_time = DateTimeUtils.now_utc() + timedelta(seconds=ttl)
        CacheUtils._cache[key] = {
            'value': value,
            'expire_time': expire_time
        }
    
    @staticmethod
    def get(key: str) -> Any:
        """Get a cache value."""
        if key not in CacheUtils._cache:
            return None
        
        entry = CacheUtils._cache[key]
        if DateTimeUtils.now_utc() > entry['expire_time']:
            # Cache expired, remove it
            del CacheUtils._cache[key]
            return None
            
        return entry['value']
    
    @staticmethod
    def delete(key: str) -> bool:
        """Delete a cache entry."""
        if key in CacheUtils._cache:
            del CacheUtils._cache[key]
            return True
        return False
    
    @staticmethod
    def clear() -> None:
        """Clear all cache entries."""
        CacheUtils._cache.clear()


class DataStructureUtils:
    """Utility functions for data structure operations."""
    
    @staticmethod
    def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten nested dictionary."""
        items: list[tuple[str, Any]] = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(DataStructureUtils.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    @staticmethod
    def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = DataStructureUtils.deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    @staticmethod
    def chunk_list(lst: List[T], chunk_size: int) -> List[List[T]]:
        """Split list into chunks of specified size."""
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
    
    @staticmethod
    def remove_none_values(d: Dict[str, Any]) -> Dict[str, Any]:
        """Remove keys with None values from dictionary."""
        return {k: v for k, v in d.items() if v is not None}


class RetryUtils:
    """Utility functions for retry logic."""
    
    @staticmethod
    def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """Calculate exponential backoff delay."""
        delay = base_delay * (2 ** attempt)
        return min(delay, max_delay)
    
    @staticmethod
    def with_retry(
        func: Callable,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: bool = True,
        exceptions: tuple = (Exception,)
    ):
        """Decorator/wrapper to retry function calls."""
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        sleep_time = RetryUtils.exponential_backoff(attempt, delay) if backoff else delay
                        logger.warning(f"Attempt {attempt + 1} failed, retrying in {sleep_time}s: {e}")
                        import time
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"All {max_attempts} attempts failed")
            
            if last_exception:
                raise last_exception
            else:
                raise Exception("All attempts failed without capturing exception")
        
        return wrapper


# Export commonly used utilities
__all__ = [
    "DateTimeUtils",
    "StringUtils", 
    "HashUtils",
    "UUIDUtils",
    "ValidationUtils",
    "SerializationUtils",
    "FileUtils",
    "CacheUtils",
    "DataStructureUtils",
    "RetryUtils"
]
