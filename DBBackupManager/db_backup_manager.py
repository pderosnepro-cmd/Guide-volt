#!/usr/bin/env python3
"""
DBBackupManager - Core Backup Module
Gestionnaire de sauvegarde multi-SGBD avec planification flexible

Support: MySQL, MariaDB, PostgreSQL, MSSQL, SQLite
"""

import os
import sys
import json
import time
import shutil
import zipfile
import tarfile
import hashlib
import logging
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


class DatabaseType(Enum):
    """Types de bases de données supportés"""
    MYSQL = "mysql"
    MARIADB = "mariadb"
    POSTGRESQL = "postgresql"
    MSSQL = "mssql"
    SQLITE = "sqlite"


class BackupFormat(Enum):
    """Formats de sauvegarde"""
    SQL = "sql"
    ZIP = "zip"
    TAR_GZ = "tar.gz"
    SEVEN_ZIP = "7z"


class CompressionLevel(Enum):
    """Niveaux de compression"""
    NONE = 0
    LOW = 1
    MEDIUM = 6
    HIGH = 9


class BackupFrequency(Enum):
    """Fréquences de sauvegarde"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


@dataclass
class DatabaseConfig:
    """Configuration d'une base de données"""
    name: str
    db_type: DatabaseType
    host: str = "localhost"
    port: int = 0
    username: str = ""
    password: str = ""
    database_name: str = ""
    
    # Pour SQLite
    file_path: str = ""
    
    # Options supplémentaires
    ssl_enabled: bool = False
    ssl_cert: str = ""
    ssl_key: str = ""
    ssl_ca: str = ""
    
    # Timeout en secondes
    timeout: int = 30
    
    def to_dict(self) -> Dict:
        """Convertir en dictionnaire"""
        return {
            "name": self.name,
            "db_type": self.db_type.value,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "database_name": self.database_name,
            "file_path": self.file_path,
            "ssl_enabled": self.ssl_enabled,
            "ssl_cert": self.ssl_cert,
            "ssl_key": self.ssl_key,
            "ssl_ca": self.ssl_ca,
            "timeout": self.timeout
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DatabaseConfig':
        """Créer depuis un dictionnaire"""
        return cls(
            name=data.get("name", ""),
            db_type=DatabaseType(data.get("db_type", "mysql")),
            host=data.get("host", "localhost"),
            port=data.get("port", 0),
            username=data.get("username", ""),
            password=data.get("password", ""),
            database_name=data.get("database_name", ""),
            file_path=data.get("file_path", ""),
            ssl_enabled=data.get("ssl_enabled", False),
            ssl_cert=data.get("ssl_cert", ""),
            ssl_key=data.get("ssl_key", ""),
            ssl_ca=data.get("ssl_ca", ""),
            timeout=data.get("timeout", 30)
        )


@dataclass
class BackupConfig:
    """Configuration d'une sauvegarde"""
    name: str
    database_name: str
    backup_path: str
    format: BackupFormat = BackupFormat.SQL
    compression_level: CompressionLevel = CompressionLevel.MEDIUM
    
    # Planification
    frequency: BackupFrequency = BackupFrequency.DAILY
    schedule_times: List[str] = field(default_factory=list)  # ["HH:MM"]
    days_of_week: List[int] = field(default_factory=list)  # 0-6 (lundi=0)
    days_of_month: List[int] = field(default_factory=list)  # 1-31
    months: List[int] = field(default_factory=list)  # 1-12
    
    # Rétention
    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 12
    keep_yearly: int = 5
    
    # Options
    include_date_in_filename: bool = True
    filename_prefix: str = "backup"
    filename_suffix: str = ""
    
    # Chiffrement
    encrypt: bool = False
    encryption_key: str = ""
    
    # Notification
    notify_on_success: bool = True
    notify_on_failure: bool = True
    email_recipients: List[str] = field(default_factory=list)
    
    # Pre/post backup commands
    pre_backup_command: str = ""
    post_backup_command: str = ""
    
    def to_dict(self) -> Dict:
        """Convertir en dictionnaire"""
        return {
            "name": self.name,
            "database_name": self.database_name,
            "backup_path": self.backup_path,
            "format": self.format.value,
            "compression_level": self.compression_level.value,
            "frequency": self.frequency.value,
            "schedule_times": self.schedule_times,
            "days_of_week": self.days_of_week,
            "days_of_month": self.days_of_month,
            "months": self.months,
            "keep_daily": self.keep_daily,
            "keep_weekly": self.keep_weekly,
            "keep_monthly": self.keep_monthly,
            "keep_yearly": self.keep_yearly,
            "include_date_in_filename": self.include_date_in_filename,
            "filename_prefix": self.filename_prefix,
            "filename_suffix": self.filename_suffix,
            "encrypt": self.encrypt,
            "encryption_key": self.encryption_key,
            "notify_on_success": self.notify_on_success,
            "notify_on_failure": self.notify_on_failure,
            "email_recipients": self.email_recipients,
            "pre_backup_command": self.pre_backup_command,
            "post_backup_command": self.post_backup_command
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BackupConfig':
        """Créer depuis un dictionnaire"""
        return cls(
            name=data.get("name", ""),
            database_name=data.get("database_name", ""),
            backup_path=data.get("backup_path", ""),
            format=BackupFormat(data.get("format", "sql")),
            compression_level=CompressionLevel(data.get("compression_level", 6)),
            frequency=BackupFrequency(data.get("frequency", "daily")),
            schedule_times=data.get("schedule_times", []),
            days_of_week=data.get("days_of_week", []),
            days_of_month=data.get("days_of_month", []),
            months=data.get("months", []),
            keep_daily=data.get("keep_daily", 7),
            keep_weekly=data.get("keep_weekly", 4),
            keep_monthly=data.get("keep_monthly", 12),
            keep_yearly=data.get("keep_yearly", 5),
            include_date_in_filename=data.get("include_date_in_filename", True),
            filename_prefix=data.get("filename_prefix", "backup"),
            filename_suffix=data.get("filename_suffix", ""),
            encrypt=data.get("encrypt", False),
            encryption_key=data.get("encryption_key", ""),
            notify_on_success=data.get("notify_on_success", True),
            notify_on_failure=data.get("notify_on_failure", True),
            email_recipients=data.get("email_recipients", []),
            pre_backup_command=data.get("pre_backup_command", ""),
            post_backup_command=data.get("post_backup_command", "")
        )


@dataclass
class BackupResult:
    """Résultat d'une sauvegarde"""
    success: bool
    backup_name: str
    database_name: str
    file_path: str
    file_size: int = 0
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    error_message: str = ""
    checksum: str = ""
    
    def duration(self) -> float:
        """Durée en secondes"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0


class BackupError(Exception):
    """Exception pour les erreurs de sauvegarde"""
    pass


# Abstract Base Class for Database Connectors
class DatabaseConnector(ABC):
    """Classe de base pour les connecteurs de base de données"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Établir la connexion"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Fermer la connexion"""
        pass
    
    @abstractmethod
    def get_databases(self) -> List[str]:
        """Lister les bases de données disponibles"""
        pass
    
    @abstractmethod
    def backup_database(self, database_name: str, output_path: str, config: BackupConfig) -> BackupResult:
        """Effectuer la sauvegarde"""
        pass
    
    @abstractmethod
    def restore_database(self, backup_path: str, database_name: str) -> bool:
        """Restaurer une sauvegarde"""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Tester la connexion"""
        pass


class MySQLConnector(DatabaseConnector):
    """Connecteur MySQL/MariaDB"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
        self.mysqldump_path = self._find_mysqldump()
    
    def _find_mysqldump(self) -> str:
        """Trouver le chemin de mysqldump"""
        paths = [
            "mysqldump",
            "/usr/bin/mysqldump",
            "/usr/local/bin/mysqldump",
            "C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin\\mysqldump.exe",
            "C:\\xampp\\mysql\\bin\\mysqldump.exe"
        ]
        for path in paths:
            if shutil.which(path) or os.path.exists(path):
                return path
        return "mysqldump"
    
    def connect(self) -> bool:
        """Tester la connexion"""
        return self.test_connection()
    
    def disconnect(self):
        """Fermer la connexion"""
        self.connection = None
    
    def get_databases(self) -> List[str]:
        """Lister les bases de données"""
        try:
            import pymysql
            conn = pymysql.connect(
                host=self.config.host,
                port=self.config.port or 3306,
                user=self.config.username,
                password=self.config.password,
                connect_timeout=self.config.timeout
            )
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            databases = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return databases
        except Exception as e:
            logging.error(f"Error listing MySQL databases: {e}")
            return []
    
    def backup_database(self, database_name: str, output_path: str, config: BackupConfig) -> BackupResult:
        """Effectuer la sauvegarde MySQL"""
        start_time = datetime.datetime.now()
        result = BackupResult(
            success=False,
            backup_name=config.name,
            database_name=database_name,
            file_path=output_path,
            start_time=start_time
        )
        
        try:
            # Créer le dossier de sortie
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Construire la commande mysqldump
            cmd = [
                self.mysqldump_path,
                f"--host={self.config.host}",
                f"--port={self.config.port or 3306}",
                f"--user={self.config.username}",
                f"--password={self.config.password}",
                database_name,
                f"--result-file={output_path}"
            ]
            
            # Options SSL
            if self.config.ssl_enabled:
                cmd.append("--ssl")
                if self.config.ssl_ca:
                    cmd.append(f"--ssl-ca={self.config.ssl_ca}")
                if self.config.ssl_cert:
                    cmd.append(f"--ssl-cert={self.config.ssl_cert}")
                if self.config.ssl_key:
                    cmd.append(f"--ssl-key={self.config.ssl_key}")
            
            # Exécuter la commande
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=config.timeout * 60)
            
            if process.returncode != 0:
                raise BackupError(f"mysqldump failed: {stderr}")
            
            # Vérifier que le fichier existe
            if not os.path.exists(output_path):
                raise BackupError(f"Backup file not created: {output_path}")
            
            # Calculer la taille et le checksum
            file_size = os.path.getsize(output_path)
            checksum = self._calculate_checksum(output_path)
            
            result.success = True
            result.file_size = file_size
            result.end_time = datetime.datetime.now()
            result.checksum = checksum
            
            logging.info(f"MySQL backup completed: {output_path} ({file_size} bytes)")
            
        except Exception as e:
            result.error_message = str(e)
            logging.error(f"MySQL backup failed: {e}")
        
        return result
    
    def restore_database(self, backup_path: str, database_name: str) -> bool:
        """Restaurer une sauvegarde MySQL"""
        try:
            # Créer la base de données si elle n'existe pas
            self._create_database(database_name)
            
            # Construire la commande mysql
            cmd = [
                "mysql",
                f"--host={self.config.host}",
                f"--port={self.config.port or 3306}",
                f"--user={self.config.username}",
                f"--password={self.config.password}",
                database_name,
                f"--execute=SOURCE {backup_path}"
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise BackupError(f"Restore failed: {stderr}")
            
            return True
            
        except Exception as e:
            logging.error(f"MySQL restore failed: {e}")
            return False
    
    def _create_database(self, database_name: str):
        """Créer une base de données"""
        try:
            import pymysql
            conn = pymysql.connect(
                host=self.config.host,
                port=self.config.port or 3306,
                user=self.config.username,
                password=self.config.password
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}`")
            cursor.close()
            conn.close()
        except Exception as e:
            logging.error(f"Error creating database {database_name}: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Tester la connexion MySQL"""
        try:
            import pymysql
            conn = pymysql.connect(
                host=self.config.host,
                port=self.config.port or 3306,
                user=self.config.username,
                password=self.config.password,
                connect_timeout=5
            )
            conn.close()
            return True
        except Exception as e:
            logging.error(f"MySQL connection test failed: {e}")
            return False
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculer le checksum MD5"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


class PostgreSQLConnector(DatabaseConnector):
    """Connecteur PostgreSQL"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
        self.pg_dump_path = self._find_pg_dump()
        self.psql_path = self._find_psql()
    
    def _find_pg_dump(self) -> str:
        """Trouver le chemin de pg_dump"""
        paths = [
            "pg_dump",
            "/usr/bin/pg_dump",
            "/usr/local/bin/pg_dump",
            "C:\\Program Files\\PostgreSQL\\15\\bin\\pg_dump.exe"
        ]
        for path in paths:
            if shutil.which(path) or os.path.exists(path):
                return path
        return "pg_dump"
    
    def _find_psql(self) -> str:
        """Trouver le chemin de psql"""
        paths = [
            "psql",
            "/usr/bin/psql",
            "/usr/local/bin/psql",
            "C:\\Program Files\\PostgreSQL\\15\\bin\\psql.exe"
        ]
        for path in paths:
            if shutil.which(path) or os.path.exists(path):
                return path
        return "psql"
    
    def connect(self) -> bool:
        """Tester la connexion"""
        return self.test_connection()
    
    def disconnect(self):
        """Fermer la connexion"""
        self.connection = None
    
    def get_databases(self) -> List[str]:
        """Lister les bases de données PostgreSQL"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port or 5432,
                user=self.config.username,
                password=self.config.password,
                connect_timeout=self.config.timeout
            )
            cursor = conn.cursor()
            cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
            databases = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return databases
        except Exception as e:
            logging.error(f"Error listing PostgreSQL databases: {e}")
            return []
    
    def backup_database(self, database_name: str, output_path: str, config: BackupConfig) -> BackupResult:
        """Effectuer la sauvegarde PostgreSQL"""
        start_time = datetime.datetime.now()
        result = BackupResult(
            success=False,
            backup_name=config.name,
            database_name=database_name,
            file_path=output_path,
            start_time=start_time
        )
        
        try:
            # Créer le dossier de sortie
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Construire la commande pg_dump
            cmd = [
                self.pg_dump_path,
                f"--host={self.config.host}",
                f"--port={self.config.port or 5432}",
                f"--username={self.config.username}",
                f"--dbname={database_name}",
                f"--file={output_path}",
                "--format=plain",
                "--verbose"
            ]
            
            # Options SSL
            if self.config.ssl_enabled:
                cmd.append("--ssl")
            
            # Environnement pour le mot de passe
            env = os.environ.copy()
            env["PGPASSWORD"] = self.config.password
            
            # Exécuter la commande
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            stdout, stderr = process.communicate(timeout=config.timeout * 60)
            
            if process.returncode != 0:
                raise BackupError(f"pg_dump failed: {stderr}")
            
            # Vérifier que le fichier existe
            if not os.path.exists(output_path):
                raise BackupError(f"Backup file not created: {output_path}")
            
            # Calculer la taille et le checksum
            file_size = os.path.getsize(output_path)
            checksum = self._calculate_checksum(output_path)
            
            result.success = True
            result.file_size = file_size
            result.end_time = datetime.datetime.now()
            result.checksum = checksum
            
            logging.info(f"PostgreSQL backup completed: {output_path} ({file_size} bytes)")
            
        except Exception as e:
            result.error_message = str(e)
            logging.error(f"PostgreSQL backup failed: {e}")
        
        return result
    
    def restore_database(self, backup_path: str, database_name: str) -> bool:
        """Restaurer une sauvegarde PostgreSQL"""
        try:
            # Créer la base de données si elle n'existe pas
            self._create_database(database_name)
            
            # Construire la commande psql
            cmd = [
                self.psql_path,
                f"--host={self.config.host}",
                f"--port={self.config.port or 5432}",
                f"--username={self.config.username}",
                f"--dbname={database_name}",
                f"--file={backup_path}"
            ]
            
            # Environnement pour le mot de passe
            env = os.environ.copy()
            env["PGPASSWORD"] = self.config.password
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise BackupError(f"Restore failed: {stderr}")
            
            return True
            
        except Exception as e:
            logging.error(f"PostgreSQL restore failed: {e}")
            return False
    
    def _create_database(self, database_name: str):
        """Créer une base de données"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port or 5432,
                user=self.config.username,
                password=self.config.password
            )
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE {database_name}")
            cursor.close()
            conn.close()
        except Exception as e:
            # Ignorer l'erreur si la base existe déjà
            if "already exists" not in str(e):
                raise
    
    def test_connection(self) -> bool:
        """Tester la connexion PostgreSQL"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port or 5432,
                user=self.config.username,
                password=self.config.password,
                connect_timeout=5
            )
            conn.close()
            return True
        except Exception as e:
            logging.error(f"PostgreSQL connection test failed: {e}")
            return False
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculer le checksum MD5"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


class MSSQLConnector(DatabaseConnector):
    """Connecteur Microsoft SQL Server"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
    
    def connect(self) -> bool:
        """Tester la connexion"""
        return self.test_connection()
    
    def disconnect(self):
        """Fermer la connexion"""
        self.connection = None
    
    def get_databases(self) -> List[str]:
        """Lister les bases de données MSSQL"""
        try:
            import pyodbc
            conn_str = self._get_connection_string()
            conn = pyodbc.connect(conn_str, timeout=self.config.timeout)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sys.databases WHERE database_id > 4")
            databases = [row.name for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return databases
        except Exception as e:
            logging.error(f"Error listing MSSQL databases: {e}")
            return []
    
    def backup_database(self, database_name: str, output_path: str, config: BackupConfig) -> BackupResult:
        """Effectuer la sauvegarde MSSQL"""
        start_time = datetime.datetime.now()
        result = BackupResult(
            success=False,
            backup_name=config.name,
            database_name=database_name,
            file_path=output_path,
            start_time=start_time
        )
        
        try:
            # Créer le dossier de sortie
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Utiliser sqlcmd ou pyodbc pour la sauvegarde
            # Méthode 1: Utiliser sqlcmd si disponible
            if self._use_sqlcmd(database_name, output_path):
                pass
            # Méthode 2: Utiliser pyodbc
            else:
                self._backup_with_pyodbc(database_name, output_path)
            
            # Vérifier que le fichier existe
            if not os.path.exists(output_path):
                raise BackupError(f"Backup file not created: {output_path}")
            
            # Calculer la taille et le checksum
            file_size = os.path.getsize(output_path)
            checksum = self._calculate_checksum(output_path)
            
            result.success = True
            result.file_size = file_size
            result.end_time = datetime.datetime.now()
            result.checksum = checksum
            
            logging.info(f"MSSQL backup completed: {output_path} ({file_size} bytes)")
            
        except Exception as e:
            result.error_message = str(e)
            logging.error(f"MSSQL backup failed: {e}")
        
        return result
    
    def _use_sqlcmd(self, database_name: str, output_path: str) -> bool:
        """Utiliser sqlcmd pour la sauvegarde"""
        try:
            # Trouver sqlcmd
            sqlcmd_paths = [
                "sqlcmd",
                "/opt/mssql-tools/bin/sqlcmd",
                "C:\\Program Files\\Microsoft SQL Server\\Client SDK\\ODBC\\170\\Tools\\Binn\\sqlcmd.exe"
            ]
            
            sqlcmd = None
            for path in sqlcmd_paths:
                if shutil.which(path) or os.path.exists(path):
                    sqlcmd = path
                    break
            
            if not sqlcmd:
                return False
            
            # Construire la commande
            cmd = [
                sqlcmd,
                "-S", f"{self.config.host},{self.config.port or 1433}",
                "-U", self.config.username,
                "-P", self.config.password,
                "-Q", f"BACKUP DATABASE [{database_name}] TO DISK = '{output_path}' WITH COMPRESSION, STATS = 10"
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise BackupError(f"sqlcmd backup failed: {stderr}")
            
            return True
            
        except Exception as e:
            logging.error(f"sqlcmd backup failed: {e}")
            return False
    
    def _backup_with_pyodbc(self, database_name: str, output_path: str):
        """Sauvegarder avec pyodbc"""
        try:
            import pyodbc
            conn_str = self._get_connection_string()
            conn = pyodbc.connect(conn_str, timeout=self.config.timeout)
            cursor = conn.cursor()
            
            # Exécuter la commande de sauvegarde
            backup_cmd = f"""
            BACKUP DATABASE [{database_name}] 
            TO DISK = '{output_path}' 
            WITH COMPRESSION, STATS = 10
            """
            cursor.execute(backup_cmd)
            cursor.close()
            conn.close()
            
        except Exception as e:
            raise BackupError(f"pyodbc backup failed: {e}")
    
    def restore_database(self, backup_path: str, database_name: str) -> bool:
        """Restaurer une sauvegarde MSSQL"""
        try:
            import pyodbc
            conn_str = self._get_connection_string()
            conn = pyodbc.connect(conn_str, timeout=self.config.timeout)
            cursor = conn.cursor()
            
            # Vérifier si la base existe et la supprimer
            cursor.execute(f"SELECT name FROM sys.databases WHERE name = '{database_name}'")
            if cursor.fetchone():
                cursor.execute(f"ALTER DATABASE [{database_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
                cursor.execute(f"DROP DATABASE [{database_name}]")
            
            # Restaurer
            restore_cmd = f"""
            RESTORE DATABASE [{database_name}] 
            FROM DISK = '{backup_path}' 
            WITH REPLACE, STATS = 10
            """
            cursor.execute(restore_cmd)
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logging.error(f"MSSQL restore failed: {e}")
            return False
    
    def _get_connection_string(self) -> str:
        """Générer la chaîne de connexion"""
        server = f"{self.config.host},{self.config.port or 1433}" if self.config.port else self.config.host
        return f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE=master;UID={self.config.username};PWD={self.config.password}"
    
    def test_connection(self) -> bool:
        """Tester la connexion MSSQL"""
        try:
            import pyodbc
            conn_str = self._get_connection_string()
            conn = pyodbc.connect(conn_str, timeout=5)
            conn.close()
            return True
        except Exception as e:
            logging.error(f"MSSQL connection test failed: {e}")
            return False
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculer le checksum MD5"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


class SQLiteConnector(DatabaseConnector):
    """Connecteur SQLite"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
    
    def connect(self) -> bool:
        """Tester la connexion"""
        return self.test_connection()
    
    def disconnect(self):
        """Fermer la connexion"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def get_databases(self) -> List[str]:
        """Lister les bases de données SQLite (fichiers)"""
        # Pour SQLite, une "base de données" est un fichier
        # Retourner le nom du fichier
        if self.config.file_path and os.path.exists(self.config.file_path):
            return [os.path.basename(self.config.file_path)]
        return []
    
    def backup_database(self, database_name: str, output_path: str, config: BackupConfig) -> BackupResult:
        """Effectuer la sauvegarde SQLite"""
        start_time = datetime.datetime.now()
        result = BackupResult(
            success=False,
            backup_name=config.name,
            database_name=database_name,
            file_path=output_path,
            start_time=start_time
        )
        
        try:
            # Créer le dossier de sortie
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Pour SQLite, la sauvegarde est une copie du fichier
            source_path = self.config.file_path
            
            if not os.path.exists(source_path):
                raise BackupError(f"Source database file not found: {source_path}")
            
            # Copier le fichier
            shutil.copy2(source_path, output_path)
            
            # Vérifier que le fichier existe
            if not os.path.exists(output_path):
                raise BackupError(f"Backup file not created: {output_path}")
            
            # Calculer la taille et le checksum
            file_size = os.path.getsize(output_path)
            checksum = self._calculate_checksum(output_path)
            
            result.success = True
            result.file_size = file_size
            result.end_time = datetime.datetime.now()
            result.checksum = checksum
            
            logging.info(f"SQLite backup completed: {output_path} ({file_size} bytes)")
            
        except Exception as e:
            result.error_message = str(e)
            logging.error(f"SQLite backup failed: {e}")
        
        return result
    
    def restore_database(self, backup_path: str, database_name: str) -> bool:
        """Restaurer une sauvegarde SQLite"""
        try:
            if not os.path.exists(backup_path):
                raise BackupError(f"Backup file not found: {backup_path}")
            
            # Copier le fichier de sauvegarde vers l'emplacement d'origine
            shutil.copy2(backup_path, self.config.file_path)
            return True
            
        except Exception as e:
            logging.error(f"SQLite restore failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Tester la connexion SQLite"""
        try:
            import sqlite3
            if not os.path.exists(self.config.file_path):
                return False
            
            conn = sqlite3.connect(self.config.file_path, timeout=5)
            conn.close()
            return True
        except Exception as e:
            logging.error(f"SQLite connection test failed: {e}")
            return False
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculer le checksum MD5"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


class BackupManager:
    """Gestionnaire principal des sauvegardes"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(PROJECT_ROOT / "config" / "config.json")
        self.schedules_path = str(PROJECT_ROOT / "config" / "schedules.json")
        self.databases: Dict[str, DatabaseConfig] = {}
        self.backups: Dict[str, BackupConfig] = {}
        self.connectors: Dict[str, DatabaseConnector] = {}
        self.logger = self._setup_logger()
        
        # Charger la configuration
        self.load_config()
    
    def _setup_logger(self) -> logging.Logger:
        """Configurer le logger"""
        logger = logging.getLogger("DBBackupManager")
        logger.setLevel(logging.INFO)
        
        # Handler pour les fichiers
        log_dir = PROJECT_ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(log_dir / "backup_manager.log")
        file_handler.setLevel(logging.INFO)
        
        # Handler pour la console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def load_config(self):
        """Charger la configuration depuis les fichiers"""
        try:
            # Charger les bases de données
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    for db_name, db_data in config_data.get("databases", {}).items():
                        self.databases[db_name] = DatabaseConfig.from_dict(db_data)
                        self._create_connector(db_name)
            
            # Charger les sauvegardes
            if os.path.exists(self.schedules_path):
                with open(self.schedules_path, 'r', encoding='utf-8') as f:
                    schedules_data = json.load(f)
                    for backup_name, backup_data in schedules_data.get("backups", {}).items():
                        self.backups[backup_name] = BackupConfig.from_dict(backup_data)
            
            self.logger.info(f"Configuration loaded: {len(self.databases)} databases, {len(self.backups)} backup schedules")
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
    
    def save_config(self):
        """Sauvegarder la configuration dans les fichiers"""
        try:
            # Sauvegarder les bases de données
            config_data = {
                "databases": {name: db.to_dict() for name, db in self.databases.items()}
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            # Sauvegarder les sauvegardes
            schedules_data = {
                "backups": {name: backup.to_dict() for name, backup in self.backups.items()}
            }
            with open(self.schedules_path, 'w', encoding='utf-8') as f:
                json.dump(schedules_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info("Configuration saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
    
    def _create_connector(self, db_name: str):
        """Créer un connecteur pour une base de données"""
        if db_name not in self.databases:
            return
        
        db_config = self.databases[db_name]
        
        if db_config.db_type == DatabaseType.MYSQL or db_config.db_type == DatabaseType.MARIADB:
            self.connectors[db_name] = MySQLConnector(db_config)
        elif db_config.db_type == DatabaseType.POSTGRESQL:
            self.connectors[db_name] = PostgreSQLConnector(db_config)
        elif db_config.db_type == DatabaseType.MSSQL:
            self.connectors[db_name] = MSSQLConnector(db_config)
        elif db_config.db_type == DatabaseType.SQLITE:
            self.connectors[db_name] = SQLiteConnector(db_config)
    
    def add_database(self, config: DatabaseConfig) -> bool:
        """Ajouter une base de données"""
        if config.name in self.databases:
            return False
        
        self.databases[config.name] = config
        self._create_connector(config.name)
        self.save_config()
        self.logger.info(f"Database added: {config.name}")
        return True
    
    def update_database(self, name: str, config: DatabaseConfig) -> bool:
        """Mettre à jour une base de données"""
        if name not in self.databases:
            return False
        
        self.databases[name] = config
        self._create_connector(name)
        self.save_config()
        self.logger.info(f"Database updated: {name}")
        return True
    
    def remove_database(self, name: str) -> bool:
        """Supprimer une base de données"""
        if name not in self.databases:
            return False
        
        del self.databases[name]
        if name in self.connectors:
            del self.connectors[name]
        
        # Supprimer les sauvegardes associées
        backup_names = [bkp_name for bkp_name, bkp in self.backups.items() if bkp.database_name == name]
        for bkp_name in backup_names:
            del self.backups[bkp_name]
        
        self.save_config()
        self.logger.info(f"Database removed: {name}")
        return True
    
    def add_backup_schedule(self, config: BackupConfig) -> bool:
        """Ajouter une planification de sauvegarde"""
        if config.name in self.backups:
            return False
        
        self.backups[config.name] = config
        self.save_config()
        self.logger.info(f"Backup schedule added: {config.name}")
        return True
    
    def update_backup_schedule(self, name: str, config: BackupConfig) -> bool:
        """Mettre à jour une planification de sauvegarde"""
        if name not in self.backups:
            return False
        
        self.backups[name] = config
        self.save_config()
        self.logger.info(f"Backup schedule updated: {name}")
        return True
    
    def remove_backup_schedule(self, name: str) -> bool:
        """Supprimer une planification de sauvegarde"""
        if name not in self.backups:
            return False
        
        del self.backups[name]
        self.save_config()
        self.logger.info(f"Backup schedule removed: {name}")
        return True
    
    def test_database_connection(self, db_name: str) -> bool:
        """Tester la connexion à une base de données"""
        if db_name not in self.connectors:
            return False
        
        return self.connectors[db_name].test_connection()
    
    def get_database_list(self, db_name: str) -> List[str]:
        """Lister les bases de données pour un connecteur"""
        if db_name not in self.connectors:
            return []
        
        return self.connectors[db_name].get_databases()
    
    def perform_backup(self, backup_name: str) -> BackupResult:
        """Effectuer une sauvegarde manuelle"""
        if backup_name not in self.backups:
            return BackupResult(
                success=False,
                backup_name=backup_name,
                database_name="",
                file_path="",
                error_message=f"Backup schedule not found: {backup_name}"
            )
        
        backup_config = self.backups[backup_name]
        
        if backup_config.database_name not in self.databases:
            return BackupResult(
                success=False,
                backup_name=backup_name,
                database_name=backup_config.database_name,
                file_path="",
                error_message=f"Database not found: {backup_config.database_name}"
            )
        
        # Générer le nom du fichier
        filename = self._generate_backup_filename(backup_config)
        output_path = os.path.join(backup_config.backup_path, filename)
        
        # Exécuter la commande pré-backup
        if backup_config.pre_backup_command:
            self._execute_command(backup_config.pre_backup_command)
        
        # Effectuer la sauvegarde
        db_config = self.databases[backup_config.database_name]
        connector = self.connectors.get(backup_config.database_name)
        
        if not connector:
            return BackupResult(
                success=False,
                backup_name=backup_name,
                database_name=backup_config.database_name,
                file_path=output_path,
                error_message=f"No connector for database: {backup_config.database_name}"
            )
        
        result = connector.backup_database(
            db_config.database_name or db_config.name,
            output_path,
            backup_config
        )
        
        # Appliquer la compression si nécessaire
        if result.success and backup_config.format != BackupFormat.SQL:
            compressed_path = self._compress_backup(output_path, backup_config)
            if compressed_path:
                # Supprimer le fichier original
                os.remove(output_path)
                result.file_path = compressed_path
                result.file_size = os.path.getsize(compressed_path)
        
        # Appliquer le chiffrement si nécessaire
        if result.success and backup_config.encrypt:
            encrypted_path = self._encrypt_backup(result.file_path, backup_config)
            if encrypted_path:
                os.remove(result.file_path)
                result.file_path = encrypted_path
        
        # Exécuter la commande post-backup
        if backup_config.post_backup_command:
            self._execute_command(backup_config.post_backup_command)
        
        # Envoyer les notifications
        if result.success and backup_config.notify_on_success:
            self._send_notification(
                backup_config,
                f"Sauvegarde réussie: {backup_name}",
                f"La sauvegarde de {backup_config.database_name} a été effectuée avec succès.\n"
                f"Fichier: {result.file_path}\n"
                f"Taille: {result.file_size} octets\n"
                f"Durée: {result.duration():.2f} secondes"
            )
        elif not result.success and backup_config.notify_on_failure:
            self._send_notification(
                backup_config,
                f"Échec de la sauvegarde: {backup_name}",
                f"La sauvegarde de {backup_config.database_name} a échoué.\n"
                f"Erreur: {result.error_message}"
            )
        
        # Appliquer la politique de rétention
        if result.success:
            self._apply_retention_policy(backup_config)
        
        return result
    
    def _generate_backup_filename(self, config: BackupConfig) -> str:
        """Générer le nom du fichier de sauvegarde"""
        timestamp = datetime.datetime.now()
        
        if config.include_date_in_filename:
            date_str = timestamp.strftime("%Y%m%d_%H%M%S")
        else:
            date_str = ""
        
        # Remplacer les espaces par des underscores
        db_name = config.database_name.replace(" ", "_")
        
        parts = []
        if config.filename_prefix:
            parts.append(config.filename_prefix)
        parts.append(db_name)
        if date_str:
            parts.append(date_str)
        if config.filename_suffix:
            parts.append(config.filename_suffix)
        
        filename = "_".join(part for part in parts if part)
        
        # Ajouter l'extension
        if config.format == BackupFormat.SQL:
            extension = ".sql"
        elif config.format == BackupFormat.ZIP:
            extension = ".zip"
        elif config.format == BackupFormat.TAR_GZ:
            extension = ".tar.gz"
        elif config.format == BackupFormat.SEVEN_ZIP:
            extension = ".7z"
        else:
            extension = ".sql"
        
        return filename + extension
    
    def _compress_backup(self, file_path: str, config: BackupConfig) -> str:
        """Compresser le fichier de sauvegarde"""
        try:
            if config.format == BackupFormat.ZIP:
                zip_path = file_path + ".zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, 
                                    compresslevel=config.compression_level.value) as zipf:
                    zipf.write(file_path, os.path.basename(file_path))
                return zip_path
            
            elif config.format == BackupFormat.TAR_GZ:
                tar_path = file_path + ".tar.gz"
                with tarfile.open(tar_path, "w:gz", 
                                compresslevel=config.compression_level.value) as tar:
                    tar.add(file_path, arcname=os.path.basename(file_path))
                return tar_path
            
            elif config.format == BackupFormat.SEVEN_ZIP:
                try:
                    import py7zr
                    sevenz_path = file_path + ".7z"
                    with py7zr.SevenZipFile(sevenz_path, 'w') as archive:
                        archive.write(file_path, os.path.basename(file_path))
                    return sevenz_path
                except ImportError:
                    self.logger.warning("py7zr not available, using zip instead")
                    return self._compress_backup(file_path, BackupConfig(
                        **config.to_dict(),
                        format=BackupFormat.ZIP
                    ))
            
        except Exception as e:
            self.logger.error(f"Compression failed: {e}")
        
        return file_path
    
    def _encrypt_backup(self, file_path: str, config: BackupConfig) -> str:
        """Chiffrer le fichier de sauvegarde"""
        try:
            from cryptography.fernet import Fernet
            
            # Générer ou utiliser la clé
            if not config.encryption_key:
                # Générer une nouvelle clé
                key = Fernet.generate_key()
                config.encryption_key = key.decode()
                self.save_config()
            else:
                key = config.encryption_key.encode()
            
            # Chiffrer le fichier
            fernet = Fernet(key)
            
            with open(file_path, 'rb') as f:
                data = f.read()
            
            encrypted_data = fernet.encrypt(data)
            
            encrypted_path = file_path + ".enc"
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            return encrypted_path
            
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
        
        return file_path
    
    def _execute_command(self, command: str):
        """Exécuter une commande système"""
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                self.logger.error(f"Command failed: {command}\nError: {stderr}")
            else:
                self.logger.info(f"Command executed: {command}")
                
        except Exception as e:
            self.logger.error(f"Error executing command: {command}\nError: {e}")
    
    def _send_notification(self, config: BackupConfig, subject: str, message: str):
        """Envoyer une notification par email"""
        if not config.email_recipients:
            return
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Configuration SMTP (à configurer dans la config)
            smtp_server = getattr(config, 'smtp_server', 'localhost')
            smtp_port = getattr(config, 'smtp_port', 587)
            smtp_username = getattr(config, 'smtp_username', '')
            smtp_password = getattr(config, 'smtp_password', '')
            smtp_use_tls = getattr(config, 'smtp_use_tls', False)
            
            # Créer le message
            msg = MIMEMultipart()
            msg['From'] = smtp_username or 'backup@localhost'
            msg['To'] = ', '.join(config.email_recipients)
            msg['Subject'] = f"[DBBackupManager] {subject}"
            msg.attach(MIMEText(message, 'plain'))
            
            # Envoyer l'email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if smtp_use_tls:
                    server.starttls()
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            self.logger.info(f"Notification sent: {subject}")
            
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
    
    def _apply_retention_policy(self, config: BackupConfig):
        """Appliquer la politique de rétention"""
        try:
            backup_dir = config.backup_path
            if not os.path.exists(backup_dir):
                return
            
            # Lister tous les fichiers de sauvegarde
            backup_files = []
            for filename in os.listdir(backup_dir):
                if filename.startswith(config.filename_prefix):
                    filepath = os.path.join(backup_dir, filename)
                    if os.path.isfile(filepath):
                        try:
                            # Extraire la date du nom de fichier
                            # Format attendu: prefix_dbname_YYYYMMDD_HHMMSS.suffix
                            parts = filename.split('_')
                            if len(parts) >= 3:
                                date_str = parts[-2] + '_' + parts[-1].split('.')[0]
                                try:
                                    file_date = datetime.datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                                    backup_files.append((filepath, file_date))
                                except ValueError:
                                    pass
                        except Exception:
                            pass
            
            # Trier par date (plus ancien en premier)
            backup_files.sort(key=lambda x: x[1])
            
            # Appliquer la rétention
            now = datetime.datetime.now()
            
            # Conserver les sauvegardes quotidiennes
            daily_cutoff = now - datetime.timedelta(days=config.keep_daily)
            # Conserver les sauvegardes hebdomadaires
            weekly_cutoff = now - datetime.timedelta(weeks=config.keep_weekly)
            # Conserver les sauvegardes mensuelles
            monthly_cutoff = now - datetime.timedelta(days=30 * config.keep_monthly)
            # Conserver les sauvegardes annuelles
            yearly_cutoff = now - datetime.timedelta(days=365 * config.keep_yearly)
            
            # Déterminer quelles sauvegardes supprimer
            files_to_delete = []
            for filepath, file_date in backup_files:
                # Garder si c'est une sauvegarde annuelle
                if file_date < yearly_cutoff and file_date.day == 1 and file_date.month == 1:
                    continue
                # Garder si c'est une sauvegarde mensuelle
                if file_date < monthly_cutoff and file_date.day == 1:
                    continue
                # Garder si c'est une sauvegarde hebdomadaire
                if file_date < weekly_cutoff and file_date.weekday() == 0:  # Lundi
                    continue
                # Garder si c'est une sauvegarde quotidienne
                if file_date < daily_cutoff:
                    files_to_delete.append(filepath)
            
            # Supprimer les fichiers
            for filepath in files_to_delete:
                try:
                    os.remove(filepath)
                    self.logger.info(f"Deleted old backup: {filepath}")
                except Exception as e:
                    self.logger.error(f"Failed to delete backup: {filepath}\nError: {e}")
            
        except Exception as e:
            self.logger.error(f"Error applying retention policy: {e}")
    
    def is_backup_due(self, backup_name: str) -> bool:
        """Vérifier si une sauvegarde est due selon la planification"""
        if backup_name not in self.backups:
            return False
        
        config = self.backups[backup_name]
        now = datetime.datetime.now()
        
        # Vérifier la fréquence
        if config.frequency == BackupFrequency.HOURLY:
            # Vérifier si l'heure actuelle correspond à une heure planifiée
            current_hour = now.hour
            for schedule_time in config.schedule_times:
                try:
                    hour = int(schedule_time.split(':')[0])
                    if current_hour == hour:
                        return True
                except ValueError:
                    pass
            return False
        
        elif config.frequency == BackupFrequency.DAILY:
            # Vérifier si l'heure actuelle correspond à une heure planifiée
            current_time = now.strftime("%H:%M")
            return current_time in config.schedule_times
        
        elif config.frequency == BackupFrequency.WEEKLY:
            # Vérifier le jour de la semaine et l'heure
            current_weekday = now.weekday()  # 0=lundi
            current_time = now.strftime("%H:%M")
            
            if current_weekday not in config.days_of_week:
                return False
            return current_time in config.schedule_times
        
        elif config.frequency == BackupFrequency.MONTHLY:
            # Vérifier le jour du mois et l'heure
            current_day = now.day
            current_time = now.strftime("%H:%M")
            
            if current_day not in config.days_of_month:
                return False
            return current_time in config.schedule_times
        
        elif config.frequency == BackupFrequency.YEARLY:
            # Vérifier le mois, le jour et l'heure
            current_month = now.month
            current_day = now.day
            current_time = now.strftime("%H:%M")
            
            if current_month not in config.months:
                return False
            if current_day not in config.days_of_month:
                return False
            return current_time in config.schedule_times
        
        elif config.frequency == BackupFrequency.CUSTOM:
            # Logique personnalisée - à implémenter selon les besoins
            # Pour l'instant, vérifier si l'heure est dans la liste
            current_time = now.strftime("%H:%M")
            return current_time in config.schedule_times
        
        return False
    
    def run_scheduled_backups(self):
        """Exécuter toutes les sauvegardes planifiées qui sont dues"""
        self.logger.info("Checking for scheduled backups...")
        
        for backup_name, config in self.backups.items():
            if self.is_backup_due(backup_name):
                self.logger.info(f"Starting scheduled backup: {backup_name}")
                result = self.perform_backup(backup_name)
                
                if result.success:
                    self.logger.info(f"Scheduled backup completed: {backup_name}")
                else:
                    self.logger.error(f"Scheduled backup failed: {backup_name} - {result.error_message}")
    
    def restore_backup(self, backup_path: str, database_name: str) -> bool:
        """Restaurer une sauvegarde"""
        # Trouver la configuration de la base de données
        db_config = None
        for name, config in self.databases.items():
            if config.name == database_name or config.database_name == database_name:
                db_config = config
                break
        
        if not db_config:
            self.logger.error(f"Database not found: {database_name}")
            return False
        
        # Trouver le connecteur
        connector = self.connectors.get(db_config.name)
        if not connector:
            self.logger.error(f"No connector for database: {database_name}")
            return False
        
        # Déchiffrer si nécessaire
        if backup_path.endswith('.enc'):
            backup_path = self._decrypt_backup(backup_path)
            if not backup_path:
                return False
        
        # Décompresser si nécessaire
        if backup_path.endswith(('.zip', '.tar.gz', '.7z')):
            backup_path = self._decompress_backup(backup_path)
            if not backup_path:
                return False
        
        # Effectuer la restauration
        return connector.restore_database(backup_path, db_config.database_name or db_config.name)
    
    def _decrypt_backup(self, file_path: str) -> str:
        """Déchiffrer un fichier de sauvegarde"""
        try:
            from cryptography.fernet import Fernet
            
            # Trouver la clé de chiffrement
            encryption_key = None
            for config in self.backups.values():
                if config.encryption_key:
                    encryption_key = config.encryption_key
                    break
            
            if not encryption_key:
                self.logger.error("No encryption key found")
                return ""
            
            fernet = Fernet(encryption_key.encode())
            
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = fernet.decrypt(encrypted_data)
            
            decrypted_path = file_path.replace('.enc', '')
            with open(decrypted_path, 'wb') as f:
                f.write(decrypted_data)
            
            return decrypted_path
            
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            return ""
    
    def _decompress_backup(self, file_path: str) -> str:
        """Décompresser un fichier de sauvegarde"""
        try:
            if file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zipf:
                    # Extraire le premier fichier
                    file_list = zipf.namelist()
                    if file_list:
                        extracted_path = os.path.join(
                            os.path.dirname(file_path),
                            file_list[0]
                        )
                        zipf.extractall(os.path.dirname(file_path))
                        return extracted_path
            
            elif file_path.endswith('.tar.gz'):
                with tarfile.open(file_path, 'r:gz') as tar:
                    file_list = tar.getnames()
                    if file_list:
                        extracted_path = os.path.join(
                            os.path.dirname(file_path),
                            file_list[0]
                        )
                        tar.extractall(os.path.dirname(file_path))
                        return extracted_path
            
            elif file_path.endswith('.7z'):
                try:
                    import py7zr
                    with py7zr.SevenZipFile(file_path, 'r') as archive:
                        file_list = archive.getnames()
                        if file_list:
                            extracted_path = os.path.join(
                                os.path.dirname(file_path),
                                file_list[0]
                            )
                            archive.extractall(os.path.dirname(file_path))
                            return extracted_path
                except ImportError:
                    self.logger.error("py7zr not available for decompression")
            
        except Exception as e:
            self.logger.error(f"Decompression failed: {e}")
        
        return ""


# Fonction utilitaire pour créer une configuration par défaut
def create_default_config():
    """Créer une configuration par défaut"""
    config_dir = PROJECT_ROOT / "config"
    config_dir.mkdir(exist_ok=True)
    
    # Configuration par défaut
    default_config = {
        "databases": {},
        "backups": {}
    }
    
    config_path = config_dir / "config.json"
    schedules_path = config_dir / "schedules.json"
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    with open(schedules_path, 'w', encoding='utf-8') as f:
        json.dump({"backups": {}}, f, indent=2, ensure_ascii=False)
    
    print(f"Default configuration created in {config_dir}")


if __name__ == "__main__":
    # Créer la configuration par défaut si elle n'existe pas
    create_default_config()
    
    # Tester le gestionnaire
    manager = BackupManager()
    print(f"DBBackupManager initialized with {len(manager.databases)} databases")
    print(f"Loaded {len(manager.backups)} backup schedules")
