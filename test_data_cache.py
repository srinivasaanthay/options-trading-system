"""
Unit tests for data cache
"""

import pytest
import tempfile
from pathlib import Path
from data_cache import DataCache


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_cache_set_get(temp_cache_dir):
    """Test basic cache set and get"""
    cache = DataCache(cache_dir=temp_cache_dir, ttl_seconds=3600)

    # Set value
    cache.set("test_key", {"data": "value"})

    # Get value
    result = cache.get("test_key")
    assert result == {"data": "value"}


def test_cache_miss(temp_cache_dir):
    """Test cache miss"""
    cache = DataCache(cache_dir=temp_cache_dir)

    result = cache.get("nonexistent_key")
    assert result is None


def test_cache_delete(temp_cache_dir):
    """Test cache deletion"""
    cache = DataCache(cache_dir=temp_cache_dir)

    cache.set("test_key", "value")
    assert cache.get("test_key") == "value"

    cache.delete("test_key")
    assert cache.get("test_key") is None


def test_cache_clear(temp_cache_dir):
    """Test clearing entire cache"""
    cache = DataCache(cache_dir=temp_cache_dir)

    cache.set("key1", "value1")
    cache.set("key2", "value2")

    cache.clear()

    assert cache.get("key1") is None
    assert cache.get("key2") is None


def test_cache_stats(temp_cache_dir):
    """Test cache statistics"""
    cache = DataCache(cache_dir=temp_cache_dir)

    cache.set("key1", "value1")
    cache.set("key2", {"data": "value2"})

    stats = cache.get_cache_stats()
    assert stats['total_entries'] == 2
    assert stats['total_size_bytes'] > 0


def test_cache_different_data_types(temp_cache_dir):
    """Test caching different data types"""
    cache = DataCache(cache_dir=temp_cache_dir)

    # String
    cache.set("str_key", "string_value")
    assert cache.get("str_key") == "string_value"

    # Dict
    cache.set("dict_key", {"a": 1, "b": 2})
    assert cache.get("dict_key") == {"a": 1, "b": 2}

    # List
    cache.set("list_key", [1, 2, 3])
    assert cache.get("list_key") == [1, 2, 3]

    # Number
    cache.set("num_key", 42)
    assert cache.get("num_key") == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
