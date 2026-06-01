#!/usr/bin/env python3
"""
DBBackupManager - Command Line Interface
Interface en ligne de commande pour la gestion des sauvegardes de bases de données
"""

import sys
import os
import json
import argparse
import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db_backup_manager import (
    BackupManager, DatabaseConfig, BackupConfig, DatabaseType, BackupFormat,
    BackupFrequency, CompressionLevel, BackupResult, create_default_config
)


class CLIColors:
    """Couleurs pour l'interface CLI"""
    
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class CLIFormatter:
    """Formateur pour l'affichage CLI"""
    
    @staticmethod
    def success(message: str) -> str:
        """Message de succès"""
        return f"{CLIColors.OKGREEN}[SUCCESS]{CLIColors.ENDC} {message}"
    
    @staticmethod
    def error(message: str) -> str:
        """Message d'erreur"""
        return f"{CLIColors.FAIL}[ERROR]{CLIColors.ENDC} {message}"
    
    @staticmethod
    def warning(message: str) -> str:
        """Message d'avertissement"""
        return f"{CLIColors.WARNING}[WARNING]{CLIColors.ENDC} {message}"
    
    @staticmethod
    def info(message: str) -> str:
        """Message d'information"""
        return f"{CLIColors.OKBLUE}[INFO]{CLIColors.ENDC} {message}"
    
    @staticmethod
    def header(title: str) -> str:
        """Titre"""
        return f"{CLIColors.HEADER}{CLIColors.BOLD}{title}{CLIColors.ENDC}"
    
    @staticmethod
    def print_backup_result(result: BackupResult):
        """Afficher le résultat d'une sauvegarde"""
        if result.success:
            print(CLIFormatter.success(f"Sauvegarde '{result.backup_name}' terminée avec succès"))
            print(f"  Base de données: {result.database_name}")
            print(f"  Fichier: {result.file_path}")
            print(f"  Taille: {result.file_size} octets")
            print(f"  Durée: {result.duration():.2f} secondes")
            if result.checksum:
                print(f"  Checksum: {result.checksum}")
        else:
            print(CLIFormatter.error(f"Sauvegarde '{result.backup_name}' échouée"))
            print(f"  Erreur: {result.error_message}")


class BackupCLI:
    """Interface en ligne de commande"""
    
    def __init__(self):
        self.manager = BackupManager()
        self.parser = self.create_parser()
        self.formatter = CLIFormatter()
        
        # Configurer le logging
        self.setup_logging()
    
    def setup_logging(self):
        """Configurer le logging pour CLI"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Créer le parseur d'arguments"""
        parser = argparse.ArgumentParser(
            description='DBBackupManager - Gestionnaire de sauvegarde multi-SGBD',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Exemples:
  dbbackup db add --name mysql_local --type mysql --host localhost --user root --password secret --database test
  dbbackup db list
  dbbackup db test mysql_local
  dbbackup backup add --name daily_backup --database mysql_local --path /backups --frequency daily --times "02:00"
  dbbackup backup run daily_backup
  dbbackup backup run-all
  dbbackup schedule check
  dbbackup restore --backup /backups/test.sql --database mysql_local
            """
        )
        
        # Sous-commandes
        subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')
        
        # Commande db (database)
        db_parser = subparsers.add_parser('db', help='Gestion des bases de données')
        db_subparsers = db_parser.add_subparsers(dest='db_command', help='Commandes de base de données')
        
        # db add
        db_add_parser = db_subparsers.add_parser('add', help='Ajouter une base de données')
        db_add_parser.add_argument('--name', required=True, help='Nom de la base de données')
        db_add_parser.add_argument('--type', required=True, 
                                   choices=['mysql', 'mariadb', 'postgresql', 'mssql', 'sqlite'],
                                   help='Type de base de données')
        db_add_parser.add_argument('--host', default='localhost', help='Hôte (par défaut: localhost)')
        db_add_parser.add_argument('--port', type=int, default=0, 
                                   help='Port (0 pour le port par défaut)')
        db_add_parser.add_argument('--user', '--username', default='', help='Nom d\'utilisateur')
        db_add_parser.add_argument('--password', default='', help='Mot de passe')
        db_add_parser.add_argument('--database', default='', help='Nom de la base de données')
        db_add_parser.add_argument('--file-path', default='', help='Chemin du fichier (SQLite)')
        db_add_parser.add_argument('--ssl', action='store_true', help='Activer SSL')
        db_add_parser.add_argument('--ssl-cert', default='', help='Certificat SSL')
        db_add_parser.add_argument('--ssl-key', default='', help='Clé SSL')
        db_add_parser.add_argument('--ssl-ca', default='', help='CA SSL')
        db_add_parser.add_argument('--timeout', type=int, default=30, help='Timeout en secondes')
        
        # db update
        db_update_parser = db_subparsers.add_parser('update', help='Modifier une base de données')
        db_update_parser.add_argument('--name', required=True, help='Nom de la base de données à modifier')
        db_update_parser.add_argument('--type', help='Type de base de données')
        db_update_parser.add_argument('--host', help='Hôte')
        db_update_parser.add_argument('--port', type=int, help='Port')
        db_update_parser.add_argument('--user', '--username', help='Nom d\'utilisateur')
        db_update_parser.add_argument('--password', help='Mot de passe')
        db_update_parser.add_argument('--database', help='Nom de la base de données')
        db_update_parser.add_argument('--file-path', help='Chemin du fichier (SQLite)')
        db_update_parser.add_argument('--ssl', action='store_true', help='Activer SSL')
        db_update_parser.add_argument('--no-ssl', action='store_false', dest='ssl', help='Désactiver SSL')
        db_update_parser.add_argument('--ssl-cert', help='Certificat SSL')
        db_update_parser.add_argument('--ssl-key', help='Clé SSL')
        db_update_parser.add_argument('--ssl-ca', help='CA SSL')
        db_update_parser.add_argument('--timeout', type=int, help='Timeout en secondes')
        
        # db remove
        db_remove_parser = db_subparsers.add_parser('remove', help='Supprimer une base de données')
        db_remove_parser.add_argument('--name', required=True, help='Nom de la base de données à supprimer')
        db_remove_parser.add_argument('--force', action='store_true', help='Forcer la suppression')
        
        # db list
        db_list_parser = db_subparsers.add_parser('list', help='Lister les bases de données')
        db_list_parser.add_argument('--verbose', '-v', action='store_true', help='Afficher les détails')
        
        # db test
        db_test_parser = db_subparsers.add_parser('test', help='Tester une connexion')
        db_test_parser.add_argument('--name', required=True, help='Nom de la base de données à tester')
        
        # db list-databases
        db_list_dbs_parser = db_subparsers.add_parser('list-databases', help='Lister les bases de données disponibles')
        db_list_dbs_parser.add_argument('--name', required=True, help='Nom de la configuration de base de données')
        
        # Commande backup
        backup_parser = subparsers.add_parser('backup', help='Gestion des sauvegardes')
        backup_subparsers = backup_parser.add_subparsers(dest='backup_command', help='Commandes de sauvegarde')
        
        # backup add
        backup_add_parser = backup_subparsers.add_parser('add', help='Ajouter une planification de sauvegarde')
        backup_add_parser.add_argument('--name', required=True, help='Nom de la planification')
        backup_add_parser.add_argument('--database', required=True, help='Nom de la base de données')
        backup_add_parser.add_argument('--path', required=True, help='Dossier de sauvegarde')
        backup_add_parser.add_argument('--format', choices=['sql', 'zip', 'tar.gz', '7z'], 
                                       default='sql', help='Format de sauvegarde')
        backup_add_parser.add_argument('--compression', choices=['none', 'low', 'medium', 'high'],
                                       default='medium', help='Niveau de compression')
        backup_add_parser.add_argument('--frequency', choices=['hourly', 'daily', 'weekly', 'monthly', 'yearly', 'custom'],
                                       default='daily', help='Fréquence de sauvegarde')
        backup_add_parser.add_argument('--times', nargs='+', default=[], help='Heures planifiées (HH:MM)')
        backup_add_parser.add_argument('--days', nargs='+', type=int, default=[], 
                                       help='Jours de la semaine (0-6, lundi=0)')
        backup_add_parser.add_argument('--month-days', nargs='+', type=int, default=[], 
                                       help='Jours du mois (1-31)')
        backup_add_parser.add_argument('--months', nargs='+', type=int, default=[], 
                                       help='Mois (1-12)')
        backup_add_parser.add_argument('--keep-daily', type=int, default=7, help='Conserver les sauvegardes quotidiennes')
        backup_add_parser.add_argument('--keep-weekly', type=int, default=4, help='Conserver les sauvegardes hebdomadaires')
        backup_add_parser.add_argument('--keep-monthly', type=int, default=12, help='Conserver les sauvegardes mensuelles')
        backup_add_parser.add_argument('--keep-yearly', type=int, default=5, help='Conserver les sauvegardes annuelles')
        backup_add_parser.add_argument('--prefix', default='backup', help='Préfixe du nom de fichier')
        backup_add_parser.add_argument('--suffix', default='', help='Suffixe du nom de fichier')
        backup_add_parser.add_argument('--no-date', action='store_false', dest='include_date', 
                                       help='Ne pas inclure la date dans le nom de fichier')
        backup_add_parser.add_argument('--encrypt', action='store_true', help='Chiffrer la sauvegarde')
        backup_add_parser.add_argument('--notify-success', action='store_true', help='Notifier en cas de succès')
        backup_add_parser.add_argument('--notify-failure', action='store_true', help='Notifier en cas d\'échec')
        backup_add_parser.add_argument('--email', nargs='+', default=[], help='Adresses email pour les notifications')
        backup_add_parser.add_argument('--pre-command', default='', help='Commande à exécuter avant la sauvegarde')
        backup_add_parser.add_argument('--post-command', default='', help='Commande à exécuter après la sauvegarde')
        
        # backup update
        backup_update_parser = backup_subparsers.add_parser('update', help='Modifier une planification de sauvegarde')
        backup_update_parser.add_argument('--name', required=True, help='Nom de la planification à modifier')
        backup_update_parser.add_argument('--database', help='Nom de la base de données')
        backup_update_parser.add_argument('--path', help='Dossier de sauvegarde')
        backup_update_parser.add_argument('--format', choices=['sql', 'zip', 'tar.gz', '7z'], help='Format de sauvegarde')
        backup_update_parser.add_argument('--compression', choices=['none', 'low', 'medium', 'high'], help='Niveau de compression')
        backup_update_parser.add_argument('--frequency', choices=['hourly', 'daily', 'weekly', 'monthly', 'yearly', 'custom'], help='Fréquence de sauvegarde')
        backup_update_parser.add_argument('--times', nargs='+', default=[], help='Heures planifiées (HH:MM)')
        backup_update_parser.add_argument('--days', nargs='+', type=int, default=[], help='Jours de la semaine (0-6)')
        backup_update_parser.add_argument('--month-days', nargs='+', type=int, default=[], help='Jours du mois (1-31)')
        backup_update_parser.add_argument('--months', nargs='+', type=int, default=[], help='Mois (1-12)')
        backup_update_parser.add_argument('--keep-daily', type=int, help='Conserver les sauvegardes quotidiennes')
        backup_update_parser.add_argument('--keep-weekly', type=int, help='Conserver les sauvegardes hebdomadaires')
        backup_update_parser.add_argument('--keep-monthly', type=int, help='Conserver les sauvegardes mensuelles')
        backup_update_parser.add_argument('--keep-yearly', type=int, help='Conserver les sauvegardes annuelles')
        backup_update_parser.add_argument('--prefix', help='Préfixe du nom de fichier')
        backup_update_parser.add_argument('--suffix', help='Suffixe du nom de fichier')
        backup_update_parser.add_argument('--no-date', action='store_false', dest='include_date', help='Ne pas inclure la date')
        backup_update_parser.add_argument('--encrypt', action='store_true', help='Chiffrer la sauvegarde')
        backup_update_parser.add_argument('--notify-success', action='store_true', help='Notifier en cas de succès')
        backup_update_parser.add_argument('--notify-failure', action='store_true', help='Notifier en cas d\'échec')
        backup_update_parser.add_argument('--email', nargs='+', default=[], help='Adresses email')
        backup_update_parser.add_argument('--pre-command', help='Commande pré-backup')
        backup_update_parser.add_argument('--post-command', help='Commande post-backup')
        
        # backup remove
        backup_remove_parser = backup_subparsers.add_parser('remove', help='Supprimer une planification de sauvegarde')
        backup_remove_parser.add_argument('--name', required=True, help='Nom de la planification à supprimer')
        backup_remove_parser.add_argument('--force', action='store_true', help='Forcer la suppression')
        
        # backup list
        backup_list_parser = backup_subparsers.add_parser('list', help='Lister les planifications de sauvegarde')
        backup_list_parser.add_argument('--verbose', '-v', action='store_true', help='Afficher les détails')
        
        # backup run
        backup_run_parser = backup_subparsers.add_parser('run', help='Exécuter une sauvegarde')
        backup_run_parser.add_argument('--name', required=True, help='Nom de la planification à exécuter')
        backup_run_parser.add_argument('--output', help='Fichier de sortie (remplace le chemin configuré)')
        
        # backup run-all
        backup_run_all_parser = backup_subparsers.add_parser('run-all', help='Exécuter toutes les sauvegardes planifiées')
        
        # Commande schedule
        schedule_parser = subparsers.add_parser('schedule', help='Gestion des planifications')
        schedule_subparsers = schedule_parser.add_subparsers(dest='schedule_command', help='Commandes de planification')
        
        # schedule check
        schedule_check_parser = schedule_subparsers.add_parser('check', help='Vérifier et exécuter les sauvegardes planifiées')
        
        # schedule list
        schedule_list_parser = schedule_subparsers.add_parser('list', help='Lister les sauvegardes planifiées')
        
        # Commande restore
        restore_parser = subparsers.add_parser('restore', help='Restaurer une sauvegarde')
        restore_parser.add_argument('--backup', required=True, help='Chemin vers le fichier de sauvegarde')
        restore_parser.add_argument('--database', required=True, help='Nom de la base de données cible')
        restore_parser.add_argument('--force', action='store_true', help='Forcer la restauration')
        
        # Commande config
        config_parser = subparsers.add_parser('config', help='Gestion de la configuration')
        config_subparsers = config_parser.add_subparsers(dest='config_command', help='Commandes de configuration')
        
        # config init
        config_init_parser = config_subparsers.add_parser('init', help='Initialiser la configuration')
        
        # config show
        config_show_parser = config_subparsers.add_parser('show', help='Afficher la configuration')
        
        # Commande info
        info_parser = subparsers.add_parser('info', help='Afficher les informations')
        
        return parser
    
    def run(self, args=None):
        """Exécuter l'interface CLI"""
        if args is None:
            args = sys.argv[1:]
        
        try:
            parsed_args = self.parser.parse_args(args)
            return self.execute_command(parsed_args)
        except argparse.ArgumentError as e:
            print(self.formatter.error(str(e)))
            return 1
        except Exception as e:
            print(self.formatter.error(f"Erreur inattendue: {str(e)}"))
            logging.exception("Erreur inattendue")
            return 1
    
    def execute_command(self, args) -> int:
        """Exécuter une commande"""
        if not hasattr(args, 'command'):
            self.parser.print_help()
            return 0
        
        command = args.command
        
        if command == 'db':
            return self.execute_db_command(args)
        elif command == 'backup':
            return self.execute_backup_command(args)
        elif command == 'schedule':
            return self.execute_schedule_command(args)
        elif command == 'restore':
            return self.execute_restore_command(args)
        elif command == 'config':
            return self.execute_config_command(args)
        elif command == 'info':
            return self.execute_info_command(args)
        else:
            self.parser.print_help()
            return 0
    
    def execute_db_command(self, args) -> int:
        """Exécuter une commande de base de données"""
        if not hasattr(args, 'db_command'):
            return 0
        
        db_command = args.db_command
        
        if db_command == 'add':
            return self.add_database(args)
        elif db_command == 'update':
            return self.update_database(args)
        elif db_command == 'remove':
            return self.remove_database(args)
        elif db_command == 'list':
            return self.list_databases(args)
        elif db_command == 'test':
            return self.test_database(args)
        elif db_command == 'list-databases':
            return self.list_database_databases(args)
        else:
            return 0
    
    def execute_backup_command(self, args) -> int:
        """Exécuter une commande de sauvegarde"""
        if not hasattr(args, 'backup_command'):
            return 0
        
        backup_command = args.backup_command
        
        if backup_command == 'add':
            return self.add_backup_schedule(args)
        elif backup_command == 'update':
            return self.update_backup_schedule(args)
        elif backup_command == 'remove':
            return self.remove_backup_schedule(args)
        elif backup_command == 'list':
            return self.list_backup_schedules(args)
        elif backup_command == 'run':
            return self.run_backup(args)
        elif backup_command == 'run-all':
            return self.run_all_backups(args)
        else:
            return 0
    
    def execute_schedule_command(self, args) -> int:
        """Exécuter une commande de planification"""
        if not hasattr(args, 'schedule_command'):
            return 0
        
        schedule_command = args.schedule_command
        
        if schedule_command == 'check':
            return self.check_scheduled_backups(args)
        elif schedule_command == 'list':
            return self.list_scheduled_backups(args)
        else:
            return 0
    
    def execute_restore_command(self, args) -> int:
        """Exécuter une commande de restauration"""
        return self.restore_backup(args)
    
    def execute_config_command(self, args) -> int:
        """Exécuter une commande de configuration"""
        if not hasattr(args, 'config_command'):
            return 0
        
        config_command = args.config_command
        
        if config_command == 'init':
            return self.init_config(args)
        elif config_command == 'show':
            return self.show_config(args)
        else:
            return 0
    
    def execute_info_command(self, args) -> int:
        """Exécuter la commande info"""
        return self.show_info()
    
    def add_database(self, args) -> int:
        """Ajouter une base de données"""
        try:
            db_type_map = {
                'mysql': DatabaseType.MYSQL,
                'mariadb': DatabaseType.MARIADB,
                'postgresql': DatabaseType.POSTGRESQL,
                'mssql': DatabaseType.MSSQL,
                'sqlite': DatabaseType.SQLITE
            }
            
            config = DatabaseConfig(
                name=args.name,
                db_type=db_type_map[args.type],
                host=args.host,
                port=args.port,
                username=args.user,
                password=args.password,
                database_name=args.database,
                file_path=args.file_path,
                ssl_enabled=args.ssl,
                ssl_cert=args.ssl_cert,
                ssl_key=args.ssl_key,
                ssl_ca=args.ssl_ca,
                timeout=args.timeout
            )
            
            if self.manager.add_database(config):
                print(self.formatter.success(f"Base de données '{args.name}' ajoutée avec succès"))
                return 0
            else:
                print(self.formatter.error(f"Une base de données avec le nom '{args.name}' existe déjà"))
                return 1
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de l'ajout de la base de données: {str(e)}"))
            return 1
    
    def update_database(self, args) -> int:
        """Modifier une base de données"""
        try:
            if args.name not in self.manager.databases:
                print(self.formatter.error(f"Base de données '{args.name}' introuvable"))
                return 1
            
            # Récupérer la configuration existante
            existing_config = self.manager.databases[args.name]
            
            # Mettre à jour les champs fournis
            if args.type:
                db_type_map = {
                    'mysql': DatabaseType.MYSQL,
                    'mariadb': DatabaseType.MARIADB,
                    'postgresql': DatabaseType.POSTGRESQL,
                    'mssql': DatabaseType.MSSQL,
                    'sqlite': DatabaseType.SQLITE
                }
                existing_config.db_type = db_type_map[args.type]
            
            if args.host:
                existing_config.host = args.host
            if args.port is not None:
                existing_config.port = args.port
            if args.user:
                existing_config.username = args.user
            if args.password:
                existing_config.password = args.password
            if args.database:
                existing_config.database_name = args.database
            if args.file_path:
                existing_config.file_path = args.file_path
            if hasattr(args, 'ssl') and args.ssl is not None:
                existing_config.ssl_enabled = args.ssl
            if args.ssl_cert:
                existing_config.ssl_cert = args.ssl_cert
            if args.ssl_key:
                existing_config.ssl_key = args.ssl_key
            if args.ssl_ca:
                existing_config.ssl_ca = args.ssl_ca
            if args.timeout:
                existing_config.timeout = args.timeout
            
            if self.manager.update_database(args.name, existing_config):
                print(self.formatter.success(f"Base de données '{args.name}' modifiée avec succès"))
                return 0
            else:
                print(self.formatter.error(f"Impossible de modifier la base de données '{args.name}'"))
                return 1
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la modification de la base de données: {str(e)}"))
            return 1
    
    def remove_database(self, args) -> int:
        """Supprimer une base de données"""
        try:
            if args.name not in self.manager.databases:
                print(self.formatter.error(f"Base de données '{args.name}' introuvable"))
                return 1
            
            if not args.force:
                response = input(f"Êtes-vous sûr de vouloir supprimer la base de données '{args.name}' ? (o/n): ")
                if response.lower() != 'o':
                    print("Suppression annulée")
                    return 0
            
            if self.manager.remove_database(args.name):
                print(self.formatter.success(f"Base de données '{args.name}' supprimée avec succès"))
                return 0
            else:
                print(self.formatter.error(f"Impossible de supprimer la base de données '{args.name}'"))
                return 1
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la suppression de la base de données: {str(e)}"))
            return 1
    
    def list_databases(self, args) -> int:
        """Lister les bases de données"""
        try:
            if not self.manager.databases:
                print("Aucune base de données configurée")
                return 0
            
            print(self.formatter.header("Bases de données configurées"))
            print("-" * 50)
            
            for name, config in self.manager.databases.items():
                if args.verbose:
                    print(f"Nom: {name}")
                    print(f"  Type: {config.db_type.value}")
                    print(f"  Hôte: {config.host}")
                    print(f"  Port: {config.port or 'par défaut'}")
                    print(f"  Utilisateur: {config.username}")
                    print(f"  Base de données: {config.database_name}")
                    print()
                else:
                    print(f"{name} ({config.db_type.value}) - {config.host}")
            
            return 0
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la liste des bases de données: {str(e)}"))
            return 1
    
    def test_database(self, args) -> int:
        """Tester une connexion de base de données"""
        try:
            if args.name not in self.manager.databases:
                print(self.formatter.error(f"Base de données '{args.name}' introuvable"))
                return 1
            
            print(f"Test de connexion pour '{args.name}'...")
            
            if self.manager.test_database_connection(args.name):
                print(self.formatter.success(f"Connexion réussie pour '{args.name}'"))
                return 0
            else:
                print(self.formatter.error(f"Échec de la connexion pour '{args.name}'"))
                return 1
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors du test de connexion: {str(e)}"))
            return 1
    
    def list_database_databases(self, args) -> int:
        """Lister les bases de données disponibles pour une configuration"""
        try:
            if args.name not in self.manager.databases:
                print(self.formatter.error(f"Base de données '{args.name}' introuvable"))
                return 1
            
            databases = self.manager.get_database_list(args.name)
            
            if not databases:
                print(f"Aucune base de données trouvée pour '{args.name}'")
                return 0
            
            print(self.formatter.header(f"Bases de données disponibles pour '{args.name}'"))
            print("-" * 50)
            
            for db in databases:
                print(f"  - {db}")
            
            return 0
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la liste des bases de données: {str(e)}"))
            return 1
    
    def add_backup_schedule(self, args) -> int:
        """Ajouter une planification de sauvegarde"""
        try:
            if args.database not in self.manager.databases:
                print(self.formatter.error(f"Base de données '{args.database}' introuvable"))
                return 1
            
            format_map = {
                'sql': BackupFormat.SQL,
                'zip': BackupFormat.ZIP,
                'tar.gz': BackupFormat.TAR_GZ,
                '7z': BackupFormat.SEVEN_ZIP
            }
            
            compression_map = {
                'none': CompressionLevel.NONE,
                'low': CompressionLevel.LOW,
                'medium': CompressionLevel.MEDIUM,
                'high': CompressionLevel.HIGH
            }
            
            frequency_map = {
                'hourly': BackupFrequency.HOURLY,
                'daily': BackupFrequency.DAILY,
                'weekly': BackupFrequency.WEEKLY,
                'monthly': BackupFrequency.MONTHLY,
                'yearly': BackupFrequency.YEARLY,
                'custom': BackupFrequency.CUSTOM
            }
            
            config = BackupConfig(
                name=args.name,
                database_name=args.database,
                backup_path=args.path,
                format=format_map[args.format],
                compression_level=compression_map[args.compression],
                frequency=frequency_map[args.frequency],
                schedule_times=args.times,
                days_of_week=args.days,
                days_of_month=args.month_days,
                months=args.months,
                keep_daily=args.keep_daily,
                keep_weekly=args.keep_weekly,
                keep_monthly=args.keep_monthly,
                keep_yearly=args.keep_yearly,
                include_date_in_filename=getattr(args, 'include_date', True),
                filename_prefix=args.prefix,
                filename_suffix=args.suffix,
                encrypt=args.encrypt,
                encryption_key="",
                notify_on_success=args.notify_success,
                notify_on_failure=args.notify_failure,
                email_recipients=args.email,
                pre_backup_command=args.pre_command,
                post_backup_command=args.post_command
            )
            
            if self.manager.add_backup_schedule(config):
                print(self.formatter.success(f"Planification '{args.name}' ajoutée avec succès"))
                return 0
            else:
                print(self.formatter.error(f"Une planification avec le nom '{args.name}' existe déjà"))
                return 1
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de l'ajout de la planification: {str(e)}"))
            return 1
    
    def update_backup_schedule(self, args) -> int:
        """Modifier une planification de sauvegarde"""
        try:
            if args.name not in self.manager.backups:
                print(self.formatter.error(f"Planification '{args.name}' introuvable"))
                return 1
            
            # Récupérer la configuration existante
            existing_config = self.manager.backups[args.name]
            
            # Mettre à jour les champs fournis
            if args.database:
                existing_config.database_name = args.database
            if args.path:
                existing_config.backup_path = args.path
            if args.format:
                format_map = {
                    'sql': BackupFormat.SQL,
                    'zip': BackupFormat.ZIP,
                    'tar.gz': BackupFormat.TAR_GZ,
                    '7z': BackupFormat.SEVEN_ZIP
                }
                existing_config.format = format_map[args.format]
            if args.compression:
                compression_map = {
                    'none': CompressionLevel.NONE,
                    'low': CompressionLevel.LOW,
                    'medium': CompressionLevel.MEDIUM,
                    'high': CompressionLevel.HIGH
                }
                existing_config.compression_level = compression_map[args.compression]
            if args.frequency:
                frequency_map = {
                    'hourly': BackupFrequency.HOURLY,
                    'daily': BackupFrequency.DAILY,
                    'weekly': BackupFrequency.WEEKLY,
                    'monthly': BackupFrequency.MONTHLY,
                    'yearly': BackupFrequency.YEARLY,
                    'custom': BackupFrequency.CUSTOM
                }
                existing_config.frequency = frequency_map[args.frequency]
            if args.times:
                existing_config.schedule_times = args.times
            if args.days:
                existing_config.days_of_week = args.days
            if args.month_days:
                existing_config.days_of_month = args.month_days
            if args.months:
                existing_config.months = args.months
            if args.keep_daily:
                existing_config.keep_daily = args.keep_daily
            if args.keep_weekly:
                existing_config.keep_weekly = args.keep_weekly
            if args.keep_monthly:
                existing_config.keep_monthly = args.keep_monthly
            if args.keep_yearly:
                existing_config.keep_yearly = args.keep_yearly
            if args.prefix:
                existing_config.filename_prefix = args.prefix
            if args.suffix:
                existing_config.filename_suffix = args.suffix
            if hasattr(args, 'include_date') and args.include_date is not None:
                existing_config.include_date_in_filename = args.include_date
            if hasattr(args, 'encrypt') and args.encrypt is not None:
                existing_config.encrypt = args.encrypt
            if hasattr(args, 'notify_success') and args.notify_success is not None:
                existing_config.notify_on_success = args.notify_success
            if hasattr(args, 'notify_failure') and args.notify_failure is not None:
                existing_config.notify_on_failure = args.notify_failure
            if args.email:
                existing_config.email_recipients = args.email
            if args.pre_command:
                existing_config.pre_backup_command = args.pre_command
            if args.post_command:
                existing_config.post_backup_command = args.post_command
            
            if self.manager.update_backup_schedule(args.name, existing_config):
                print(self.formatter.success(f"Planification '{args.name}' modifiée avec succès"))
                return 0
            else:
                print(self.formatter.error(f"Impossible de modifier la planification '{args.name}'"))
                return 1
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la modification de la planification: {str(e)}"))
            return 1
    
    def remove_backup_schedule(self, args) -> int:
        """Supprimer une planification de sauvegarde"""
        try:
            if args.name not in self.manager.backups:
                print(self.formatter.error(f"Planification '{args.name}' introuvable"))
                return 1
            
            if not args.force:
                response = input(f"Êtes-vous sûr de vouloir supprimer la planification '{args.name}' ? (o/n): ")
                if response.lower() != 'o':
                    print("Suppression annulée")
                    return 0
            
            if self.manager.remove_backup_schedule(args.name):
                print(self.formatter.success(f"Planification '{args.name}' supprimée avec succès"))
                return 0
            else:
                print(self.formatter.error(f"Impossible de supprimer la planification '{args.name}'"))
                return 1
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la suppression de la planification: {str(e)}"))
            return 1
    
    def list_backup_schedules(self, args) -> int:
        """Lister les planifications de sauvegarde"""
        try:
            if not self.manager.backups:
                print("Aucune planification de sauvegarde configurée")
                return 0
            
            print(self.formatter.header("Planifications de sauvegarde"))
            print("-" * 50)
            
            for name, config in self.manager.backups.items():
                if args.verbose:
                    print(f"Nom: {name}")
                    print(f"  Base de données: {config.database_name}")
                    print(f"  Dossier: {config.backup_path}")
                    print(f"  Fréquence: {config.frequency.value}")
                    print(f"  Heures: {', '.join(config.schedule_times) if config.schedule_times else 'Aucune'}")
                    print(f"  Format: {config.format.value}")
                    print(f"  Compression: {config.compression_level.name}")
                    print(f"  Rétention: {config.keep_daily}j / {config.keep_weekly}s / {config.keep_monthly}m / {config.keep_yearly}a")
                    print()
                else:
                    print(f"{name} - {config.database_name} ({config.frequency.value})")
            
            return 0
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la liste des planifications: {str(e)}"))
            return 1
    
    def run_backup(self, args) -> int:
        """Exécuter une sauvegarde"""
        try:
            if args.name not in self.manager.backups:
                print(self.formatter.error(f"Planification '{args.name}' introuvable"))
                return 1
            
            print(f"Exécution de la sauvegarde '{args.name}'...")
            
            # Si un chemin de sortie est spécifié, mettre à jour temporairement la configuration
            if args.output:
                # Sauvegarder la configuration originale
                original_config = self.manager.backups[args.name]
                original_path = original_config.backup_path
                
                # Mettre à jour le chemin
                original_config.backup_path = os.path.dirname(args.output)
                self.manager.backups[args.name] = original_config
            
            result = self.manager.perform_backup(args.name)
            
            # Restaurer le chemin original
            if args.output:
                original_config.backup_path = original_path
                self.manager.backups[args.name] = original_config
            
            CLIFormatter.print_backup_result(result)
            
            return 0 if result.success else 1
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de l'exécution de la sauvegarde: {str(e)}"))
            return 1
    
    def run_all_backups(self, args) -> int:
        """Exécuter toutes les sauvegardes planifiées"""
        try:
            print("Exécution de toutes les sauvegardes planifiées...")
            self.manager.run_scheduled_backups()
            print(self.formatter.success("Toutes les sauvegardes planifiées ont été exécutées"))
            return 0
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de l'exécution des sauvegardes: {str(e)}"))
            return 1
    
    def check_scheduled_backups(self, args) -> int:
        """Vérifier et exécuter les sauvegardes planifiées"""
        try:
            print("Vérification des sauvegardes planifiées...")
            
            executed = False
            for backup_name in self.manager.backups.keys():
                if self.manager.is_backup_due(backup_name):
                    print(f"Sauvegarde '{backup_name}' est due, exécution...")
                    result = self.manager.perform_backup(backup_name)
                    CLIFormatter.print_backup_result(result)
                    executed = True
            
            if not executed:
                print("Aucune sauvegarde planifiée n'est due")
            
            return 0
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la vérification des sauvegardes: {str(e)}"))
            return 1
    
    def list_scheduled_backups(self, args) -> int:
        """Lister les sauvegardes planifiées"""
        try:
            print(self.formatter.header("Sauvegardes planifiées"))
            print("-" * 50)
            
            now = datetime.datetime.now()
            
            for name, config in self.manager.backups.items():
                is_due = self.manager.is_backup_due(name)
                status = "DUE" if is_due else "OK"
                
                print(f"{name}: {status}")
                print(f"  Prochaine exécution: {self.get_next_execution_time(config)}")
                print()
            
            return 0
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la liste des sauvegardes planifiées: {str(e)}"))
            return 1
    
    def get_next_execution_time(self, config: BackupConfig) -> str:
        """Obtenir le prochain temps d'exécution"""
        now = datetime.datetime.now()
        
        if config.frequency == BackupFrequency.HOURLY:
            # Trouver la prochaine heure planifiée
            for time_str in config.schedule_times:
                try:
                    hour = int(time_str.split(':')[0])
                    if hour >= now.hour:
                        next_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                    else:
                        next_time = now.replace(hour=hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                    return next_time.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, IndexError):
                    pass
        
        elif config.frequency == BackupFrequency.DAILY:
            # Trouver la prochaine heure planifiée
            for time_str in config.schedule_times:
                try:
                    hour, minute = map(int, time_str.split(':'))
                    if (hour > now.hour) or (hour == now.hour and minute >= now.minute):
                        next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    else:
                        next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + datetime.timedelta(days=1)
                    return next_time.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, IndexError):
                    pass
        
        elif config.frequency == BackupFrequency.WEEKLY:
            # Trouver le prochain jour et heure
            for day in config.days_of_week:
                for time_str in config.schedule_times:
                    try:
                        hour, minute = map(int, time_str.split(':'))
                        # Calculer le prochain jour
                        days_ahead = (day - now.weekday()) % 7
                        if days_ahead == 0 and (hour > now.hour or (hour == now.hour and minute >= now.minute)):
                            next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        else:
                            next_time = now + datetime.timedelta(days=days_ahead)
                            next_time = next_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        return next_time.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, IndexError):
                        pass
        
        elif config.frequency == BackupFrequency.MONTHLY:
            # Trouver le prochain jour du mois et heure
            for day in config.days_of_month:
                for time_str in config.schedule_times:
                    try:
                        hour, minute = map(int, time_str.split(':'))
                        # Calculer le prochain jour
                        if day > now.day:
                            next_time = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
                        elif day == now.day and (hour > now.hour or (hour == now.hour and minute >= now.minute)):
                            next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        else:
                            # Passer au mois suivant
                            next_month = now.month + 1 if now.month < 12 else 1
                            next_year = now.year + 1 if next_month == 1 else now.year
                            next_time = now.replace(year=next_year, month=next_month, day=day, 
                                                   hour=hour, minute=minute, second=0, microsecond=0)
                        return next_time.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, IndexError):
                        pass
        
        elif config.frequency == BackupFrequency.YEARLY:
            # Trouver le prochain mois, jour et heure
            for month in config.months:
                for day in config.days_of_month:
                    for time_str in config.schedule_times:
                        try:
                            hour, minute = map(int, time_str.split(':'))
                            # Calculer la prochaine date
                            if month > now.month:
                                next_time = now.replace(month=month, day=day, hour=hour, minute=minute, 
                                                       second=0, microsecond=0)
                            elif month == now.month:
                                if day > now.day:
                                    next_time = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
                                elif day == now.day and (hour > now.hour or (hour == now.hour and minute >= now.minute)):
                                    next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                                else:
                                    next_time = now.replace(year=now.year + 1, month=month, day=day,
                                                           hour=hour, minute=minute, second=0, microsecond=0)
                            else:
                                next_time = now.replace(year=now.year + 1, month=month, day=day,
                                                       hour=hour, minute=minute, second=0, microsecond=0)
                            return next_time.strftime("%Y-%m-%d %H:%M:%S")
                        except (ValueError, IndexError):
                            pass
        
        return "Inconnu"
    
    def restore_backup(self, args) -> int:
        """Restaurer une sauvegarde"""
        try:
            if not os.path.exists(args.backup):
                print(self.formatter.error(f"Fichier de sauvegarde '{args.backup}' introuvable"))
                return 1
            
            if args.database not in self.manager.databases:
                print(self.formatter.error(f"Base de données '{args.database}' introuvable"))
                return 1
            
            if not args.force:
                response = input(f"Êtes-vous sûr de vouloir restaurer '{args.backup}' vers '{args.database}' ? (o/n): ")
                if response.lower() != 'o':
                    print("Restauration annulée")
                    return 0
            
            print(f"Restauration de '{args.backup}' vers '{args.database}'...")
            
            if self.manager.restore_backup(args.backup, args.database):
                print(self.formatter.success(f"Restauration terminée avec succès"))
                return 0
            else:
                print(self.formatter.error(f"Échec de la restauration"))
                return 1
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de la restauration: {str(e)}"))
            return 1
    
    def init_config(self, args) -> int:
        """Initialiser la configuration"""
        try:
            create_default_config()
            print(self.formatter.success("Configuration initialisée avec succès"))
            return 0
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de l'initialisation: {str(e)}"))
            return 1
    
    def show_config(self, args) -> int:
        """Afficher la configuration"""
        try:
            print(self.formatter.header("Configuration actuelle"))
            print("-" * 50)
            
            print("\nBases de données:")
            for name, config in self.manager.databases.items():
                print(f"  {name}:")
                print(f"    Type: {config.db_type.value}")
                print(f"    Hôte: {config.host}")
                print(f"    Port: {config.port or 'par défaut'}")
                print(f"    Utilisateur: {config.username}")
                print(f"    Base: {config.database_name}")
            
            print("\nPlanifications de sauvegarde:")
            for name, config in self.manager.backups.items():
                print(f"  {name}:")
                print(f"    Base: {config.database_name}")
                print(f"    Dossier: {config.backup_path}")
                print(f"    Fréquence: {config.frequency.value}")
                print(f"    Heures: {', '.join(config.schedule_times) if config.schedule_times else 'Aucune'}")
            
            return 0
                
        except Exception as e:
            print(self.formatter.error(f"Erreur lors de l'affichage de la configuration: {str(e)}"))
            return 1
    
    def show_info(self) -> int:
        """Afficher les informations"""
        print(self.formatter.header("DBBackupManager"))
        print("-" * 50)
        print("Gestionnaire de sauvegarde multi-SGBD avec planification flexible")
        print()
        print("Version: 1.0.0")
        print("Support: MySQL, MariaDB, PostgreSQL, MSSQL, SQLite")
        print()
        print("Bases de données configurées:", len(self.manager.databases))
        print("Planifications de sauvegarde:", len(self.manager.backups))
        print()
        print("Utilisation:")
        print("  dbbackup [commande] [options]")
        print()
        print("Commandes disponibles:")
        print("  db          - Gestion des bases de données")
        print("  backup      - Gestion des sauvegardes")
        print("  schedule    - Gestion des planifications")
        print("  restore     - Restaurer une sauvegarde")
        print("  config      - Gestion de la configuration")
        print("  info        - Afficher les informations")
        print()
        print("Utilisez 'dbbackup [commande] --help' pour plus d'informations")
        
        return 0


def main():
    """Fonction principale"""
    cli = BackupCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
