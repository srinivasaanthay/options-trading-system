"""
Logging Configuration and Setup
Centralized logging for the application
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
import sys


class LoggerSetup:
    """Configure and manage application logging"""

    _configured = False

    @staticmethod
    def setup(
        log_dir: str = "logs",
        log_file: str = "stock_agent.log",
        level: str = "INFO",
        max_size: int = 10485760,  # 10 MB
        backup_count: int = 5,
        format_string: Optional[str] = None
    ) -> logging.Logger:
        """
        Configure logging for the application

        Args:
            log_dir: Directory for log files
            log_file: Name of log file
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            max_size: Max size of log file before rotation (bytes)
            backup_count: Number of backup log files to keep
            format_string: Custom log format

        Returns:
            Configured root logger
        """
        if LoggerSetup._configured:
            return logging.getLogger()

        # Create log directory
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper()))

        # Log format
        if format_string is None:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        formatter = logging.Formatter(format_string)

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_path / log_file,
            maxBytes=max_size,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Console handler for WARNING and above
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        LoggerSetup._configured = True
        return root_logger

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Get logger for a specific module"""
        return logging.getLogger(name)


# Convenience function
def setup_logging(
    log_dir: str = "logs",
    log_file: str = "stock_agent.log",
    level: str = "INFO"
) -> logging.Logger:
    """Setup logging and return root logger"""
    return LoggerSetup.setup(log_dir, log_file, level)


def get_logger(name: str) -> logging.Logger:
    """Get logger for a module"""
    return LoggerSetup.get_logger(name)
