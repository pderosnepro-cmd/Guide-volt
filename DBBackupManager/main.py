#!/usr/bin/env python3
"""
DBBackupManager - Main Entry Point
Point d'entrée principal pour le logiciel de sauvegarde
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(
        description='DBBackupManager - Gestionnaire de sauvegarde multi-SGBD'
    )
    
    # Mode d'exécution
    parser.add_argument(
        '--mode', 
        choices=['gui', 'cli', 'daemon'],
        default='gui',
        help='Mode d\'exécution: gui (interface graphique), cli (ligne de commande), daemon (service)'
    )
    
    # Arguments pour le mode daemon
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Intervalle de vérification en secondes (pour le mode daemon)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'gui':
        run_gui()
    elif args.mode == 'cli':
        run_cli()
    elif args.mode == 'daemon':
        run_daemon(args.interval)
    else:
        # Par défaut, démarrer l'interface graphique
        run_gui()


def run_gui():
    """Démarrer l'interface graphique"""
    try:
        from gui.backup_gui import MainWindow
        from PyQt6.QtWidgets import QApplication
        
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())
        
    except ImportError as e:
        print(f"Erreur: Impossible de démarrer l'interface graphique: {e}")
        print("Assurez-vous que PyQt6 est installé: pip install PyQt6")
        sys.exit(1)


def run_cli():
    """Démarrer l'interface ligne de commande"""
    try:
        from cli.backup_cli import main as cli_main
        sys.exit(cli_main())
        
    except ImportError as e:
        print(f"Erreur: Impossible de démarrer l'interface CLI: {e}")
        sys.exit(1)


def run_daemon(interval: int = 60):
    """Démarrer en mode daemon (service)"""
    try:
        from db_backup_manager import BackupManager
        import time
        import logging
        
        # Configurer le logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/backup_daemon.log'),
                logging.StreamHandler()
            ]
        )
        
        manager = BackupManager()
        logging.info(f"DBBackupManager daemon démarré avec un intervalle de {interval} secondes")
        
        while True:
            try:
                logging.info("Vérification des sauvegardes planifiées...")
                manager.run_scheduled_backups()
                
                # Attendre l'intervalle suivant
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logging.info("Arrêt du daemon...")
                break
            except Exception as e:
                logging.error(f"Erreur dans le daemon: {e}")
                time.sleep(60)  # Attendre avant de réessayer
        
    except ImportError as e:
        print(f"Erreur: Impossible de démarrer le daemon: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
