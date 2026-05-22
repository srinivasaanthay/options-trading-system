"""
Configuration Management System
Handles loading and managing YAML configuration with environment variable substitution
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager with environment variable support"""

    def __init__(self, config_file: str = "config.yaml"):
        """
        Initialize configuration from YAML file

        Args:
            config_file: Path to config.yaml file
        """
        self.config_path = Path(config_file)
        self._config = self._load_config()
        self._substitute_env_vars()
        logger.info(f"Configuration loaded from {config_file}")

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML configuration file"""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return {}

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config if config else {}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    def _substitute_env_vars(self) -> None:
        """Replace ${VAR_NAME} with environment variables"""
        def substitute(obj):
            if isinstance(obj, dict):
                return {k: substitute(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute(item) for item in obj]
            elif isinstance(obj, str):
                # Replace ${VAR_NAME} patterns with environment variables
                if obj.startswith('${') and obj.endswith('}'):
                    var_name = obj[2:-1]
                    return os.getenv(var_name, obj)
                return obj
            return obj

        self._config = substitute(self._config)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        Example: config.get('api.massive_com.api_key')

        Args:
            key: Dot-notation key path
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def get_dict(self, section: str) -> Dict[str, Any]:
        """Get entire section as dictionary"""
        return self.get(section, {})

    def validate_required(self, *keys: str) -> bool:
        """Validate that required configuration keys are present"""
        missing = []
        for key in keys:
            if self.get(key) is None:
                missing.append(key)

        if missing:
            logger.error(f"Missing required configuration: {', '.join(missing)}")
            return False
        return True

    def __repr__(self) -> str:
        """String representation (sanitized to hide secrets)"""
        return f"<Config: {len(self._config)} sections>"

    def to_dict(self) -> Dict[str, Any]:
        """Get full configuration as dictionary"""
        return self._config.copy()


# Global configuration instance
_config_instance: Optional[Config] = None


def load_config(config_file: str = "config.yaml") -> Config:
    """Load or get global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_file)
    return _config_instance


def get_config() -> Config:
    """Get the current configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
