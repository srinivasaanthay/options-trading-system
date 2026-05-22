"""
Data Caching Layer
Manages caching of API responses and market data
"""

import logging
import json
import pickle
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class DataCache:
    """Simple file-based data cache with TTL support"""

    def __init__(self, cache_dir: str = "data/cache", ttl_seconds: int = 3600):
        """
        Initialize cache

        Args:
            cache_dir: Directory for cache files
            ttl_seconds: Time-to-live for cache entries
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """Generate cache file path from key"""
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hash_key}.cache"

    def _get_metadata_path(self, cache_path: Path) -> Path:
        """Get metadata file path"""
        return cache_path.with_suffix('.meta')

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        try:
            cache_path = self._get_cache_path(key)

            if not cache_path.exists():
                return None

            # Check TTL
            meta_path = self._get_metadata_path(cache_path)
            if meta_path.exists():
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                    timestamp = datetime.fromisoformat(meta['timestamp'])
                    if datetime.now() - timestamp > timedelta(seconds=self.ttl_seconds):
                        # Cache expired
                        cache_path.unlink()
                        meta_path.unlink()
                        return None

            # Load cached data
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
                logger.debug(f"Cache hit: {key}")
                return data

        except Exception as e:
            logger.error(f"Error reading cache for {key}: {e}")
            return None

    def set(self, key: str, value: Any) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache

        Returns:
            True if successful
        """
        try:
            cache_path = self._get_cache_path(key)
            meta_path = self._get_metadata_path(cache_path)

            # Save data
            with open(cache_path, 'wb') as f:
                pickle.dump(value, f)

            # Save metadata
            meta = {
                'timestamp': datetime.now().isoformat(),
                'key': key
            }
            with open(meta_path, 'w') as f:
                json.dump(meta, f)

            logger.debug(f"Cached: {key}")
            return True

        except Exception as e:
            logger.error(f"Error writing cache for {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete cache entry"""
        try:
            cache_path = self._get_cache_path(key)
            meta_path = self._get_metadata_path(cache_path)

            if cache_path.exists():
                cache_path.unlink()
            if meta_path.exists():
                meta_path.unlink()

            return True
        except Exception as e:
            logger.error(f"Error deleting cache for {key}: {e}")
            return False

    def clear(self) -> bool:
        """Clear entire cache"""
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            for meta_file in self.cache_dir.glob("*.meta"):
                meta_file.unlink()

            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False

    def cleanup_expired(self) -> int:
        """Remove expired cache entries"""
        cleaned = 0
        try:
            for meta_file in self.cache_dir.glob("*.meta"):
                try:
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                        timestamp = datetime.fromisoformat(meta['timestamp'])
                        if datetime.now() - timestamp > timedelta(seconds=self.ttl_seconds):
                            cache_file = meta_file.with_suffix('.cache')
                            if cache_file.exists():
                                cache_file.unlink()
                            meta_file.unlink()
                            cleaned += 1
                except Exception as e:
                    logger.warning(f"Error processing {meta_file}: {e}")

            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} expired cache entries")

            return cleaned
        except Exception as e:
            logger.error(f"Error in cache cleanup: {e}")
            return 0

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        cache_files = list(self.cache_dir.glob("*.cache"))
        meta_files = list(self.cache_dir.glob("*.meta"))

        return {
            'total_entries': len(cache_files),
            'total_size_bytes': sum(f.stat().st_size for f in cache_files),
            'metadata_files': len(meta_files)
        }
