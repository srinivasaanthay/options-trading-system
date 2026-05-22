"""
Unit tests for configuration management
"""

import pytest
import os
from pathlib import Path
from config import Config, load_config, get_config


def test_config_load():
    """Test loading configuration"""
    config = Config("config.yaml")
    assert config is not None


def test_config_get():
    """Test getting configuration values"""
    config = Config("config.yaml")

    # Test existing keys
    api_key = config.get('api.massive_com.api_key')
    assert api_key is not None or api_key == "${MASSIVE_COM_API_KEY}"

    # Test nested keys
    timeout = config.get('api.massive_com.timeout')
    assert isinstance(timeout, int)


def test_config_get_with_default():
    """Test getting non-existent keys with default"""
    config = Config("config.yaml")

    value = config.get('non.existent.key', 'default_value')
    assert value == 'default_value'


def test_config_global_instance():
    """Test global config instance"""
    config1 = get_config()
    config2 = get_config()

    assert config1 is config2


def test_config_to_dict():
    """Test converting config to dictionary"""
    config = Config("config.yaml")
    config_dict = config.to_dict()

    assert isinstance(config_dict, dict)
    assert 'api' in config_dict


def test_config_validate_required():
    """Test validation of required keys"""
    config = Config("config.yaml")

    # Existing key
    assert config.validate_required('api.massive_com.timeout')

    # Non-existing key
    assert not config.validate_required('non.existent.key')
