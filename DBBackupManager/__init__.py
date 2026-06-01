#!/usr/bin/env python3
"""
DBBackupManager - Package Initialization
"""

__version__ = "1.0.0"
__author__ = "DBBackupManager Team"
__description__ = "Multi-DB Backup Manager with Flexible Scheduling"

from .db_backup_manager import (
    BackupManager,
    DatabaseConfig,
    BackupConfig,
    DatabaseType,
    BackupFormat,
    BackupFrequency,
    CompressionLevel,
    BackupResult,
    BackupError,
    create_default_config
)

__all__ = [
    "BackupManager",
    "DatabaseConfig",
    "BackupConfig",
    "DatabaseType",
    "BackupFormat",
    "BackupFrequency",
    "CompressionLevel",
    "BackupResult",
    "BackupError",
    "create_default_config",
    "__version__",
    "__author__",
    "__description__"
]
