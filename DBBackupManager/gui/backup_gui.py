#!/usr/bin/env python3
"""
DBBackupManager - Graphical User Interface
Interface graphique pour la gestion des sauvegardes de bases de données
"""

import sys
import os
import json
import threading
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit, QListWidget,
    QListWidgetItem, QTabWidget, QGroupBox, QCheckBox, QSpinBox, QTimeEdit,
    QDateEdit, QMessageBox, QInputDialog, QFileDialog, QProgressBar,
    QFormLayout, QFrame, QSplitter
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QObject, QSize, QDate, QTime
)
from PyQt6.QtGui import (
    QIcon, QFont, QPalette, QColor, QPixmap, QAction
)

from db_backup_manager import (
    BackupManager, DatabaseConfig, BackupConfig, DatabaseType, BackupFormat,
    BackupFrequency, CompressionLevel, BackupResult
)


class BackupWorker(QObject):
    """Worker thread pour les opérations de sauvegarde"""
    
    finished = pyqtSignal(BackupResult)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, manager: BackupManager):
        super().__init__()
        self.manager = manager
        self._is_running = False
    
    def run_backup(self, backup_name: str):
        """Exécuter une sauvegarde"""
        self._is_running = True
        try:
            self.progress.emit(f"Démarrage de la sauvegarde: {backup_name}")
            result = self.manager.perform_backup(backup_name)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._is_running = False
    
    def run_scheduled_backups(self):
        """Exécuter toutes les sauvegardes planifiées"""
        self._is_running = True
        try:
            self.progress.emit("Vérification des sauvegardes planifiées...")
            self.manager.run_scheduled_backups()
            self.finished.emit(BackupResult(
                success=True,
                backup_name="scheduled",
                database_name="all",
                file_path="",
                error_message=""
            ))
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._is_running = False
    
    def test_connection(self, db_name: str):
        """Tester une connexion"""
        try:
            result = self.manager.test_database_connection(db_name)
            if result:
                self.finished.emit(BackupResult(
                    success=True,
                    backup_name="connection_test",
                    database_name=db_name,
                    file_path="",
                    error_message=""
                ))
            else:
                self.error.emit(f"Échec du test de connexion pour {db_name}")
        except Exception as e:
            self.error.emit(str(e))


class DatabaseDialog(QDialog):
    """Dialogue pour ajouter/modifier une base de données"""
    
    def __init__(self, parent=None, db_config=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter/Modifier une base de données")
        self.setMinimumSize(400, 500)
        
        self.db_config = db_config
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        # Nom
        self.name_edit = QLineEdit()
        layout.addRow("Nom:", self.name_edit)
        
        # Type de base de données
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "MySQL", "MariaDB", "PostgreSQL", "MSSQL", "SQLite"
        ])
        layout.addRow("Type:", self.type_combo)
        
        # Hôte
        self.host_edit = QLineEdit("localhost")
        layout.addRow("Hôte:", self.host_edit)
        
        # Port
        self.port_spin = QSpinBox()
        self.port_spin.setRange(0, 65535)
        self.port_spin.setValue(3306)
        layout.addRow("Port:", self.port_spin)
        
        # Nom d'utilisateur
        self.username_edit = QLineEdit()
        layout.addRow("Nom d'utilisateur:", self.username_edit)
        
        # Mot de passe
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Mot de passe:", self.password_edit)
        
        # Nom de la base de données
        self.database_edit = QLineEdit()
        layout.addRow("Nom de la base:", self.database_edit)
        
        # Chemin du fichier (SQLite)
        self.file_path_edit = QLineEdit()
        self.file_path_button = QPushButton("Parcourir...")
        self.file_path_button.clicked.connect(self.browse_file)
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.file_path_button)
        layout.addRow("Chemin du fichier (SQLite):", file_layout)
        
        # SSL
        self.ssl_check = QCheckBox("Activer SSL")
        layout.addRow(self.ssl_check)
        
        # Certificat SSL
        self.ssl_cert_edit = QLineEdit()
        layout.addRow("Certificat SSL:", self.ssl_cert_edit)
        
        # Clé SSL
        self.ssl_key_edit = QLineEdit()
        layout.addRow("Clé SSL:", self.ssl_key_edit)
        
        # CA SSL
        self.ssl_ca_edit = QLineEdit()
        layout.addRow("CA SSL:", self.ssl_ca_edit)
        
        # Timeout
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setValue(30)
        layout.addRow("Timeout (secondes):", self.timeout_spin)
        
        # Boutons
        button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Annuler")
        button_box.addWidget(self.ok_button)
        button_box.addWidget(self.cancel_button)
        layout.addRow(button_box)
        
        # Connexions
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        # Charger la configuration existante
        if self.db_config:
            self.load_config()
        
        # Masquer les champs SQLite par défaut
        self.update_ui_for_db_type()
        self.type_combo.currentIndexChanged.connect(self.update_ui_for_db_type)
    
    def update_ui_for_db_type(self):
        """Mettre à jour l'UI selon le type de base de données"""
        db_type = self.type_combo.currentText()
        
        # Masquer les champs SQLite pour les autres types
        show_sqlite_fields = db_type == "SQLite"
        self.file_path_edit.setVisible(show_sqlite_fields)
        self.file_path_button.setVisible(show_sqlite_fields)
        
        # Mettre à jour les ports par défaut
        if db_type == "MySQL" or db_type == "MariaDB":
            self.port_spin.setValue(3306)
        elif db_type == "PostgreSQL":
            self.port_spin.setValue(5432)
        elif db_type == "MSSQL":
            self.port_spin.setValue(1433)
        elif db_type == "SQLite":
            self.port_spin.setValue(0)
    
    def browse_file(self):
        """Parcourir pour sélectionner un fichier"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier SQLite", "", "SQLite Files (*.sqlite *.db *.sqlite3)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
    
    def load_config(self):
        """Charger la configuration existante"""
        if not self.db_config:
            return
        
        self.name_edit.setText(self.db_config.name)
        
        # Trouver l'index du type
        type_index = self.type_combo.findText(
            self.db_config.db_type.value.capitalize()
        )
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)
        
        self.host_edit.setText(self.db_config.host)
        self.port_spin.setValue(self.db_config.port or 0)
        self.username_edit.setText(self.db_config.username)
        self.password_edit.setText(self.db_config.password)
        self.database_edit.setText(self.db_config.database_name)
        self.file_path_edit.setText(self.db_config.file_path)
        self.ssl_check.setChecked(self.db_config.ssl_enabled)
        self.ssl_cert_edit.setText(self.db_config.ssl_cert)
        self.ssl_key_edit.setText(self.db_config.ssl_key)
        self.ssl_ca_edit.setText(self.db_config.ssl_ca)
        self.timeout_spin.setValue(self.db_config.timeout)
    
    def get_config(self) -> DatabaseConfig:
        """Obtenir la configuration"""
        db_type_map = {
            "MySQL": DatabaseType.MYSQL,
            "MariaDB": DatabaseType.MARIADB,
            "PostgreSQL": DatabaseType.POSTGRESQL,
            "MSSQL": DatabaseType.MSSQL,
            "SQLite": DatabaseType.SQLITE
        }
        
        return DatabaseConfig(
            name=self.name_edit.text().strip(),
            db_type=db_type_map[self.type_combo.currentText()],
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            username=self.username_edit.text().strip(),
            password=self.password_edit.text().strip(),
            database_name=self.database_edit.text().strip(),
            file_path=self.file_path_edit.text().strip(),
            ssl_enabled=self.ssl_check.isChecked(),
            ssl_cert=self.ssl_cert_edit.text().strip(),
            ssl_key=self.ssl_key_edit.text().strip(),
            ssl_ca=self.ssl_ca_edit.text().strip(),
            timeout=self.timeout_spin.value()
        )


class BackupScheduleDialog(QDialog):
    """Dialogue pour ajouter/modifier une planification de sauvegarde"""
    
    def __init__(self, parent=None, backup_config=None, database_names=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter/Modifier une planification de sauvegarde")
        self.setMinimumSize(500, 600)
        
        self.backup_config = backup_config
        self.database_names = database_names or []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        # Nom
        self.name_edit = QLineEdit()
        layout.addRow("Nom:", self.name_edit)
        
        # Base de données
        self.db_combo = QComboBox()
        self.db_combo.addItems(self.database_names)
        layout.addRow("Base de données:", self.db_combo)
        
        # Dossier de sauvegarde
        self.path_edit = QLineEdit()
        self.path_button = QPushButton("Parcourir...")
        self.path_button.clicked.connect(self.browse_path)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.path_button)
        layout.addRow("Dossier de sauvegarde:", path_layout)
        
        # Format
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "SQL", "ZIP", "TAR.GZ", "7Z"
        ])
        layout.addRow("Format:", self.format_combo)
        
        # Niveau de compression
        self.compression_combo = QComboBox()
        self.compression_combo.addItems([
            "Aucun", "Faible", "Moyen", "Élevé"
        ])
        layout.addRow("Compression:", self.compression_combo)
        
        # Fréquence
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems([
            "Horaires", "Quotidienne", "Hebdomadaire", "Mensuelle", "Annuelle", "Personnalisée"
        ])
        self.frequency_combo.currentIndexChanged.connect(self.update_schedule_ui)
        layout.addRow("Fréquence:", self.frequency_combo)
        
        # Heures planifiées
        self.times_list = QListWidget()
        self.add_time_button = QPushButton("+")
        self.add_time_button.clicked.connect(self.add_time)
        self.remove_time_button = QPushButton("-")
        self.remove_time_button.clicked.connect(self.remove_time)
        
        time_layout = QHBoxLayout()
        time_layout.addWidget(self.times_list)
        time_layout.addWidget(self.add_time_button)
        time_layout.addWidget(self.remove_time_button)
        layout.addRow("Heures planifiées:", time_layout)
        
        # Jours de la semaine (pour hebdomadaire)
        self.weekdays_group = QGroupBox("Jours de la semaine")
        self.weekdays_layout = QHBoxLayout()
        self.weekday_checks = []
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        for i, day in enumerate(days):
            check = QCheckBox(day)
            self.weekday_checks.append(check)
            self.weekdays_layout.addWidget(check)
        self.weekdays_group.setLayout(self.weekdays_layout)
        layout.addRow(self.weekdays_group)
        
        # Jours du mois (pour mensuelle)
        self.monthdays_group = QGroupBox("Jours du mois")
        self.monthdays_layout = QHBoxLayout()
        self.monthday_checks = []
        for i in range(1, 32):
            check = QCheckBox(str(i))
            self.monthday_checks.append(check)
            self.monthdays_layout.addWidget(check)
        self.monthdays_group.setLayout(self.monthdays_layout)
        layout.addRow(self.monthdays_group)
        
        # Mois (pour annuelle)
        self.months_group = QGroupBox("Mois")
        self.months_layout = QHBoxLayout()
        self.month_checks = []
        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", 
                  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        for i, month in enumerate(months):
            check = QCheckBox(month)
            self.month_checks.append(check)
            self.months_layout.addWidget(check)
        self.months_group.setLayout(self.months_layout)
        layout.addRow(self.months_group)
        
        # Préfixe du nom de fichier
        self.prefix_edit = QLineEdit("backup")
        layout.addRow("Préfixe du fichier:", self.prefix_edit)
        
        # Suffixe du nom de fichier
        self.suffix_edit = QLineEdit()
        layout.addRow("Suffixe du fichier:", self.suffix_edit)
        
        # Inclure la date dans le nom
        self.include_date_check = QCheckBox("Inclure la date dans le nom de fichier")
        self.include_date_check.setChecked(True)
        layout.addRow(self.include_date_check)
        
        # Chiffrement
        self.encrypt_check = QCheckBox("Chiffrer la sauvegarde")
        layout.addRow(self.encrypt_check)
        
        # Notification
        self.notify_success_check = QCheckBox("Notifier en cas de succès")
        self.notify_success_check.setChecked(True)
        layout.addRow(self.notify_success_check)
        
        self.notify_failure_check = QCheckBox("Notifier en cas d'échec")
        self.notify_failure_check.setChecked(True)
        layout.addRow(self.notify_failure_check)
        
        # Email
        self.email_edit = QLineEdit()
        layout.addRow("Emails (séparés par des virgules):", self.email_edit)
        
        # Politique de rétention
        retention_group = QGroupBox("Politique de rétention")
        retention_layout = QGridLayout()
        
        self.keep_daily_spin = QSpinBox()
        self.keep_daily_spin.setRange(0, 365)
        self.keep_daily_spin.setValue(7)
        retention_layout.addWidget(QLabel("Conserver quotidiennes:"), 0, 0)
        retention_layout.addWidget(self.keep_daily_spin, 0, 1)
        
        self.keep_weekly_spin = QSpinBox()
        self.keep_weekly_spin.setRange(0, 52)
        self.keep_weekly_spin.setValue(4)
        retention_layout.addWidget(QLabel("Conserver hebdomadaires:"), 1, 0)
        retention_layout.addWidget(self.keep_weekly_spin, 1, 1)
        
        self.keep_monthly_spin = QSpinBox()
        self.keep_monthly_spin.setRange(0, 120)
        self.keep_monthly_spin.setValue(12)
        retention_layout.addWidget(QLabel("Conserver mensuelles:"), 2, 0)
        retention_layout.addWidget(self.keep_monthly_spin, 2, 1)
        
        self.keep_yearly_spin = QSpinBox()
        self.keep_yearly_spin.setRange(0, 100)
        self.keep_yearly_spin.setValue(5)
        retention_layout.addWidget(QLabel("Conserver annuelles:"), 3, 0)
        retention_layout.addWidget(self.keep_yearly_spin, 3, 1)
        
        retention_group.setLayout(retention_layout)
        layout.addRow(retention_group)
        
        # Commandes pré/post backup
        self.pre_command_edit = QLineEdit()
        layout.addRow("Commande pré-backup:", self.pre_command_edit)
        
        self.post_command_edit = QLineEdit()
        layout.addRow("Commande post-backup:", self.post_command_edit)
        
        # Boutons
        button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Annuler")
        button_box.addWidget(self.ok_button)
        button_box.addWidget(self.cancel_button)
        layout.addRow(button_box)
        
        # Connexions
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        # Charger la configuration existante
        if self.backup_config:
            self.load_config()
        
        # Mettre à jour l'UI selon la fréquence
        self.update_schedule_ui()
    
    def update_schedule_ui(self):
        """Mettre à jour l'UI selon la fréquence sélectionnée"""
        frequency = self.frequency_combo.currentText()
        
        # Masquer tous les groupes de planification
        self.weekdays_group.setVisible(False)
        self.monthdays_group.setVisible(False)
        self.months_group.setVisible(False)
        
        if frequency == "Hebdomadaire":
            self.weekdays_group.setVisible(True)
        elif frequency == "Mensuelle":
            self.monthdays_group.setVisible(True)
        elif frequency == "Annuelle":
            self.monthdays_group.setVisible(True)
            self.months_group.setVisible(True)
    
    def browse_path(self):
        """Parcourir pour sélectionner un dossier"""
        path = QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier de sauvegarde"
        )
        if path:
            self.path_edit.setText(path)
    
    def add_time(self):
        """Ajouter une heure"""
        time, ok = QInputDialog.getText(
            self, "Ajouter une heure", "Heure (HH:MM):"
        )
        if ok and time:
            # Valider le format
            if len(time) == 5 and time[2] == ':':
                try:
                    hour = int(time[:2])
                    minute = int(time[3:])
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        self.times_list.addItem(time)
                except ValueError:
                    pass
    
    def remove_time(self):
        """Supprimer une heure"""
        for item in self.times_list.selectedItems():
            self.times_list.takeItem(self.times_list.row(item))
    
    def load_config(self):
        """Charger la configuration existante"""
        if not self.backup_config:
            return
        
        self.name_edit.setText(self.backup_config.name)
        
        # Trouver l'index de la base de données
        db_index = self.db_combo.findText(self.backup_config.database_name)
        if db_index >= 0:
            self.db_combo.setCurrentIndex(db_index)
        
        self.path_edit.setText(self.backup_config.backup_path)
        
        # Format
        format_index = self.format_combo.findText(self.backup_config.format.value.upper())
        if format_index >= 0:
            self.format_combo.setCurrentIndex(format_index)
        
        # Compression
        compression_map = {
            CompressionLevel.NONE: 0,
            CompressionLevel.LOW: 1,
            CompressionLevel.MEDIUM: 2,
            CompressionLevel.HIGH: 3
        }
        compression_index = compression_map.get(self.backup_config.compression_level, 2)
        self.compression_combo.setCurrentIndex(compression_index)
        
        # Fréquence
        frequency_index = self.frequency_combo.findText(
            self.backup_config.frequency.value.capitalize()
        )
        if frequency_index >= 0:
            self.frequency_combo.setCurrentIndex(frequency_index)
        
        # Heures
        for time_str in self.backup_config.schedule_times:
            self.times_list.addItem(time_str)
        
        # Jours de la semaine
        for i, check in enumerate(self.weekday_checks):
            check.setChecked(i in self.backup_config.days_of_week)
        
        # Jours du mois
        for i, check in enumerate(self.monthday_checks):
            check.setChecked((i + 1) in self.backup_config.days_of_month)
        
        # Mois
        for i, check in enumerate(self.month_checks):
            check.setChecked((i + 1) in self.backup_config.months)
        
        self.prefix_edit.setText(self.backup_config.filename_prefix)
        self.suffix_edit.setText(self.backup_config.filename_suffix)
        self.include_date_check.setChecked(self.backup_config.include_date_in_filename)
        self.encrypt_check.setChecked(self.backup_config.encrypt)
        self.notify_success_check.setChecked(self.backup_config.notify_on_success)
        self.notify_failure_check.setChecked(self.backup_config.notify_on_failure)
        self.email_edit.setText(', '.join(self.backup_config.email_recipients))
        
        self.keep_daily_spin.setValue(self.backup_config.keep_daily)
        self.keep_weekly_spin.setValue(self.backup_config.keep_weekly)
        self.keep_monthly_spin.setValue(self.backup_config.keep_monthly)
        self.keep_yearly_spin.setValue(self.backup_config.keep_yearly)
        
        self.pre_command_edit.setText(self.backup_config.pre_backup_command)
        self.post_command_edit.setText(self.backup_config.post_backup_command)
        
        # Mettre à jour l'UI
        self.update_schedule_ui()
    
    def get_config(self) -> BackupConfig:
        """Obtenir la configuration"""
        format_map = {
            "SQL": BackupFormat.SQL,
            "ZIP": BackupFormat.ZIP,
            "TAR.GZ": BackupFormat.TAR_GZ,
            "7Z": BackupFormat.SEVEN_ZIP
        }
        
        compression_map = {
            0: CompressionLevel.NONE,
            1: CompressionLevel.LOW,
            2: CompressionLevel.MEDIUM,
            3: CompressionLevel.HIGH
        }
        
        frequency_map = {
            "Horaires": BackupFrequency.HOURLY,
            "Quotidienne": BackupFrequency.DAILY,
            "Hebdomadaire": BackupFrequency.WEEKLY,
            "Mensuelle": BackupFrequency.MONTHLY,
            "Annuelle": BackupFrequency.YEARLY,
            "Personnalisée": BackupFrequency.CUSTOM
        }
        
        # Heures
        times = []
        for i in range(self.times_list.count()):
            item = self.times_list.item(i)
            times.append(item.text())
        
        # Jours de la semaine
        weekdays = []
        for i, check in enumerate(self.weekday_checks):
            if check.isChecked():
                weekdays.append(i)
        
        # Jours du mois
        monthdays = []
        for i, check in enumerate(self.monthday_checks):
            if check.isChecked():
                monthdays.append(i + 1)
        
        # Mois
        months = []
        for i, check in enumerate(self.month_checks):
            if check.isChecked():
                months.append(i + 1)
        
        # Emails
        emails = [e.strip() for e in self.email_edit.text().split(',') if e.strip()]
        
        return BackupConfig(
            name=self.name_edit.text().strip(),
            database_name=self.db_combo.currentText(),
            backup_path=self.path_edit.text().strip(),
            format=format_map[self.format_combo.currentText()],
            compression_level=compression_map[self.compression_combo.currentIndex()],
            frequency=frequency_map[self.frequency_combo.currentText()],
            schedule_times=times,
            days_of_week=weekdays,
            days_of_month=monthdays,
            months=months,
            keep_daily=self.keep_daily_spin.value(),
            keep_weekly=self.keep_weekly_spin.value(),
            keep_monthly=self.keep_monthly_spin.value(),
            keep_yearly=self.keep_yearly_spin.value(),
            include_date_in_filename=self.include_date_check.isChecked(),
            filename_prefix=self.prefix_edit.text().strip(),
            filename_suffix=self.suffix_edit.text().strip(),
            encrypt=self.encrypt_check.isChecked(),
            encryption_key="",  # Sera générée si nécessaire
            notify_on_success=self.notify_success_check.isChecked(),
            notify_on_failure=self.notify_failure_check.isChecked(),
            email_recipients=emails,
            pre_backup_command=self.pre_command_edit.text().strip(),
            post_backup_command=self.post_command_edit.text().strip()
        )


class MainWindow(QMainWindow):
    """Fenêtre principale de l'application"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DBBackupManager")
        self.setMinimumSize(1024, 768)
        
        # Initialiser le gestionnaire de sauvegarde
        self.manager = BackupManager()
        
        # Worker thread
        self.worker_thread = QThread()
        self.worker = BackupWorker(self.manager)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run_scheduled_backups)
        
        # Connexions du worker
        self.worker.finished.connect(self.on_backup_finished)
        self.worker.progress.connect(self.on_backup_progress)
        self.worker.error.connect(self.on_backup_error)
        
        # Démarrer le thread
        self.worker_thread.start()
        
        # Timer pour vérifier les sauvegardes planifiées
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_scheduled_backups)
        self.timer.start(60000)  # Vérifier toutes les minutes
        
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        """Configurer l'interface utilisateur"""
        # Menu
        self.create_menu()
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QHBoxLayout(central_widget)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Panneau de gauche (navigation)
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        
        # Boutons de navigation
        self.nav_buttons = {
            "databases": QPushButton("Bases de données"),
            "backups": QPushButton("Planifications"),
            "history": QPushButton("Historique"),
            "settings": QPushButton("Paramètres")
        }
        
        for name, button in self.nav_buttons.items():
            button.setCheckable(True)
            button.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 8px;
                    border: none;
                    background: transparent;
                }
                QPushButton:checked {
                    background: #e0e0e0;
                    border-left: 3px solid #0078d7;
                }
            """)
            button.clicked.connect(lambda checked, n=name: self.show_page(n))
            left_layout.addWidget(button)
        
        # Sélectionner le premier bouton
        self.nav_buttons["databases"].setChecked(True)
        
        # Panneau de droite (contenu)
        self.right_panel = QTabWidget()
        self.right_panel.setTabPosition(QTabWidget.TabPosition.North)
        
        # Pages
        self.pages = {
            "databases": self.create_databases_page(),
            "backups": self.create_backups_page(),
            "history": self.create_history_page(),
            "settings": self.create_settings_page()
        }
        
        for name, page in self.pages.items():
            self.right_panel.addTab(page, name.capitalize())
        
        # Ajouter au splitter
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        
        # Barre de statut
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Barre d'outils
        self.create_toolbar()
    
    def create_menu(self):
        """Créer le menu"""
        menubar = self.menuBar()
        
        # Menu Fichier
        file_menu = menubar.addMenu("Fichier")
        
        new_db_action = QAction("Nouvelle base de données", self)
        new_db_action.triggered.connect(self.add_database)
        file_menu.addAction(new_db_action)
        
        new_backup_action = QAction("Nouvelle planification", self)
        new_backup_action.triggered.connect(self.add_backup_schedule)
        file_menu.addAction(new_backup_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Quitter", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menu Outils
        tools_menu = menubar.addMenu("Outils")
        
        run_backups_action = QAction("Exécuter les sauvegardes planifiées", self)
        run_backups_action.triggered.connect(self.run_scheduled_backups)
        tools_menu.addAction(run_backups_action)
        
        # Menu Aide
        help_menu = menubar.addMenu("Aide")
        
        about_action = QAction("À propos", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_toolbar(self):
        """Créer la barre d'outils"""
        toolbar = self.addToolBar("Barre d'outils")
        
        # Bouton Exécuter
        run_action = QAction("Exécuter", self)
        run_action.triggered.connect(self.run_selected_backup)
        toolbar.addAction(run_action)
        
        # Bouton Tester la connexion
        test_action = QAction("Tester la connexion", self)
        test_action.triggered.connect(self.test_selected_connection)
        toolbar.addAction(test_action)
        
        # Séparateur
        toolbar.addSeparator()
        
        # Bouton Rafraîchir
        refresh_action = QAction("Rafraîchir", self)
        refresh_action.triggered.connect(self.load_data)
        toolbar.addAction(refresh_action)
    
    def create_databases_page(self) -> QWidget:
        """Créer la page des bases de données"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Barre d'outils
        toolbar = QHBoxLayout()
        
        self.add_db_button = QPushButton("Ajouter")
        self.add_db_button.clicked.connect(self.add_database)
        toolbar.addWidget(self.add_db_button)
        
        self.edit_db_button = QPushButton("Modifier")
        self.edit_db_button.clicked.connect(self.edit_database)
        toolbar.addWidget(self.edit_db_button)
        
        self.delete_db_button = QPushButton("Supprimer")
        self.delete_db_button.clicked.connect(self.delete_database)
        toolbar.addWidget(self.delete_db_button)
        
        self.test_db_button = QPushButton("Tester la connexion")
        self.test_db_button.clicked.connect(self.test_selected_connection)
        toolbar.addWidget(self.test_db_button)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Liste des bases de données
        self.databases_list = QListWidget()
        self.databases_list.itemDoubleClicked.connect(self.edit_database)
        self.databases_list.itemSelectionChanged.connect(self.on_database_selection_changed)
        layout.addWidget(self.databases_list)
        
        # Détails
        self.db_details_group = QGroupBox("Détails")
        self.db_details_layout = QFormLayout()
        
        self.db_name_label = QLabel()
        self.db_type_label = QLabel()
        self.db_host_label = QLabel()
        self.db_port_label = QLabel()
        self.db_username_label = QLabel()
        self.db_database_label = QLabel()
        
        self.db_details_layout.addRow("Nom:", self.db_name_label)
        self.db_details_layout.addRow("Type:", self.db_type_label)
        self.db_details_layout.addRow("Hôte:", self.db_host_label)
        self.db_details_layout.addRow("Port:", self.db_port_label)
        self.db_details_layout.addRow("Utilisateur:", self.db_username_label)
        self.db_details_layout.addRow("Base de données:", self.db_database_label)
        
        self.db_details_group.setLayout(self.db_details_layout)
        layout.addWidget(self.db_details_group)
        
        return page
    
    def create_backups_page(self) -> QWidget:
        """Créer la page des planifications"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Barre d'outils
        toolbar = QHBoxLayout()
        
        self.add_backup_button = QPushButton("Ajouter")
        self.add_backup_button.clicked.connect(self.add_backup_schedule)
        toolbar.addWidget(self.add_backup_button)
        
        self.edit_backup_button = QPushButton("Modifier")
        self.edit_backup_button.clicked.connect(self.edit_backup_schedule)
        toolbar.addWidget(self.edit_backup_button)
        
        self.delete_backup_button = QPushButton("Supprimer")
        self.delete_backup_button.clicked.connect(self.delete_backup_schedule)
        toolbar.addWidget(self.delete_backup_button)
        
        self.run_backup_button = QPushButton("Exécuter")
        self.run_backup_button.clicked.connect(self.run_selected_backup)
        toolbar.addWidget(self.run_backup_button)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Liste des planifications
        self.backups_list = QListWidget()
        self.backups_list.itemDoubleClicked.connect(self.edit_backup_schedule)
        self.backups_list.itemSelectionChanged.connect(self.on_backup_selection_changed)
        layout.addWidget(self.backups_list)
        
        # Détails
        self.backup_details_group = QGroupBox("Détails")
        self.backup_details_layout = QFormLayout()
        
        self.backup_name_label = QLabel()
        self.backup_db_label = QLabel()
        self.backup_path_label = QLabel()
        self.backup_frequency_label = QLabel()
        self.backup_times_label = QLabel()
        self.backup_format_label = QLabel()
        
        self.backup_details_layout.addRow("Nom:", self.backup_name_label)
        self.backup_details_layout.addRow("Base de données:", self.backup_db_label)
        self.backup_details_layout.addRow("Dossier:", self.backup_path_label)
        self.backup_details_layout.addRow("Fréquence:", self.backup_frequency_label)
        self.backup_details_layout.addRow("Heures:", self.backup_times_label)
        self.backup_details_layout.addRow("Format:", self.backup_format_label)
        
        self.backup_details_group.setLayout(self.backup_details_layout)
        layout.addWidget(self.backup_details_group)
        
        # Progression
        self.progress_group = QGroupBox("Progression")
        self.progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        
        self.progress_label = QLabel("Prêt")
        
        self.progress_layout.addWidget(self.progress_bar)
        self.progress_layout.addWidget(self.progress_label)
        self.progress_group.setLayout(self.progress_layout)
        layout.addWidget(self.progress_group)
        
        return page
    
    def create_history_page(self) -> QWidget:
        """Créer la page d'historique"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Filtre
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filtre:"))
        self.history_filter_combo = QComboBox()
        self.history_filter_combo.addItems(["Tous", "Succès", "Échecs"])
        filter_layout.addWidget(self.history_filter_combo)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Liste de l'historique
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        
        # Détails
        self.history_details_group = QGroupBox("Détails")
        self.history_details_layout = QFormLayout()
        
        self.history_type_label = QLabel()
        self.history_db_label = QLabel()
        self.history_time_label = QLabel()
        self.history_size_label = QLabel()
        self.history_file_label = QLabel()
        self.history_status_label = QLabel()
        
        self.history_details_layout.addRow("Type:", self.history_type_label)
        self.history_details_layout.addRow("Base de données:", self.history_db_label)
        self.history_details_layout.addRow("Heure:", self.history_time_label)
        self.history_details_layout.addRow("Taille:", self.history_size_label)
        self.history_details_layout.addRow("Fichier:", self.history_file_label)
        self.history_details_layout.addRow("Statut:", self.history_status_label)
        
        self.history_details_group.setLayout(self.history_details_layout)
        layout.addWidget(self.history_details_group)
        
        return page
    
    def create_settings_page(self) -> QWidget:
        """Créer la page des paramètres"""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Paramètres généraux
        general_group = QGroupBox("Paramètres généraux")
        general_layout = QFormLayout()
        
        # Langue
        self.language_combo = QComboBox()
        self.language_combo.addItems(["Français", "English"])
        general_layout.addRow("Langue:", self.language_combo)
        
        # Thème
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Clair", "Sombre", "Système"])
        general_layout.addRow("Thème:", self.theme_combo)
        
        general_group.setLayout(general_layout)
        layout.addWidget(general_group)
        
        # Paramètres SMTP
        smtp_group = QGroupBox("Paramètres SMTP")
        smtp_layout = QFormLayout()
        
        self.smtp_server_edit = QLineEdit()
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(587)
        self.smtp_username_edit = QLineEdit()
        self.smtp_password_edit = QLineEdit()
        self.smtp_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_tls_check = QCheckBox("Utiliser TLS")
        
        smtp_layout.addRow("Serveur:", self.smtp_server_edit)
        smtp_layout.addRow("Port:", self.smtp_port_spin)
        smtp_layout.addRow("Utilisateur:", self.smtp_username_edit)
        smtp_layout.addRow("Mot de passe:", self.smtp_password_edit)
        smtp_layout.addRow(self.smtp_tls_check)
        
        smtp_group.setLayout(smtp_layout)
        layout.addWidget(smtp_group)
        
        # Boutons
        button_box = QHBoxLayout()
        button_box.addStretch()
        save_button = QPushButton("Sauvegarder")
        save_button.clicked.connect(self.save_settings)
        button_box.addWidget(save_button)
        layout.addLayout(button_box)
        
        return page
    
    def load_data(self):
        """Charger les données"""
        # Charger les bases de données
        self.databases_list.clear()
        for name, config in self.manager.databases.items():
            item = QListWidgetItem(f"{name} ({config.db_type.value})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.databases_list.addItem(item)
        
        # Charger les planifications
        self.backups_list.clear()
        for name, config in self.manager.backups.items():
            item = QListWidgetItem(f"{name} - {config.database_name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.backups_list.addItem(item)
        
        # Charger l'historique (à implémenter)
        self.load_history()
    
    def load_history(self):
        """Charger l'historique"""
        # Pour l'instant, on simule un historique
        # Dans une version complète, cela viendrait d'une base de données ou d'un fichier
        self.history_list.clear()
        
        # Ajouter quelques entrées de test
        for i in range(5):
            item = QListWidgetItem(f"Sauvegarde {i+1} - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.history_list.addItem(item)
    
    def show_page(self, page_name: str):
        """Afficher une page"""
        # Désélectionner tous les boutons
        for button in self.nav_buttons.values():
            button.setChecked(False)
        
        # Sélectionner le bouton correspondant
        if page_name in self.nav_buttons:
            self.nav_buttons[page_name].setChecked(True)
        
        # Afficher l'onglet correspondant
        self.right_panel.setCurrentIndex(list(self.pages.keys()).index(page_name))
    
    def add_database(self):
        """Ajouter une base de données"""
        dialog = DatabaseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            if config.name:
                if self.manager.add_database(config):
                    self.load_data()
                    QMessageBox.information(self, "Succès", "Base de données ajoutée avec succès")
                else:
                    QMessageBox.warning(self, "Erreur", "Une base de données avec ce nom existe déjà")
    
    def edit_database(self):
        """Modifier une base de données"""
        selected_items = self.databases_list.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        db_name = item.data(Qt.ItemDataRole.UserRole)
        
        if db_name not in self.manager.databases:
            return
        
        config = self.manager.databases[db_name]
        dialog = DatabaseDialog(self, config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.get_config()
            if new_config.name:
                if self.manager.update_database(db_name, new_config):
                    self.load_data()
                    QMessageBox.information(self, "Succès", "Base de données modifiée avec succès")
                else:
                    QMessageBox.warning(self, "Erreur", "Impossible de modifier la base de données")
    
    def delete_database(self):
        """Supprimer une base de données"""
        selected_items = self.databases_list.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        db_name = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer la base de données '{db_name}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.manager.remove_database(db_name):
                self.load_data()
                QMessageBox.information(self, "Succès", "Base de données supprimée avec succès")
            else:
                QMessageBox.warning(self, "Erreur", "Impossible de supprimer la base de données")
    
    def test_selected_connection(self):
        """Tester la connexion sélectionnée"""
        selected_items = self.databases_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner une base de données")
            return
        
        item = selected_items[0]
        db_name = item.data(Qt.ItemDataRole.UserRole)
        
        self.progress_label.setText(f"Test de connexion pour {db_name}...")
        self.progress_bar.setValue(0)
        
        # Exécuter le test dans un thread
        test_thread = QThread()
        test_worker = BackupWorker(self.manager)
        test_worker.moveToThread(test_thread)
        
        test_thread.started.connect(lambda: test_worker.test_connection(db_name))
        test_worker.finished.connect(lambda result: self.on_test_finished(result, db_name))
        test_worker.error.connect(lambda error: self.on_test_error(error, db_name))
        
        test_thread.start()
    
    def on_test_finished(self, result: BackupResult, db_name: str):
        """Gérer la fin du test de connexion"""
        if result.success:
            self.progress_label.setText(f"Connexion réussie pour {db_name}")
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Succès", f"Connexion réussie pour {db_name}")
        else:
            self.on_test_error(result.error_message, db_name)
    
    def on_test_error(self, error: str, db_name: str):
        """Gérer l'erreur du test de connexion"""
        self.progress_label.setText(f"Échec de la connexion pour {db_name}")
        self.progress_bar.setValue(0)
        QMessageBox.warning(self, "Erreur", f"Échec de la connexion pour {db_name}: {error}")
    
    def add_backup_schedule(self):
        """Ajouter une planification de sauvegarde"""
        if not self.manager.databases:
            QMessageBox.warning(self, "Erreur", "Veuillez d'abord ajouter une base de données")
            return
        
        dialog = BackupScheduleDialog(
            self,
            database_names=list(self.manager.databases.keys())
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            if config.name:
                if self.manager.add_backup_schedule(config):
                    self.load_data()
                    QMessageBox.information(self, "Succès", "Planification ajoutée avec succès")
                else:
                    QMessageBox.warning(self, "Erreur", "Une planification avec ce nom existe déjà")
    
    def edit_backup_schedule(self):
        """Modifier une planification de sauvegarde"""
        selected_items = self.backups_list.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        backup_name = item.data(Qt.ItemDataRole.UserRole)
        
        if backup_name not in self.manager.backups:
            return
        
        config = self.manager.backups[backup_name]
        dialog = BackupScheduleDialog(
            self,
            config,
            database_names=list(self.manager.databases.keys())
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.get_config()
            if new_config.name:
                if self.manager.update_backup_schedule(backup_name, new_config):
                    self.load_data()
                    QMessageBox.information(self, "Succès", "Planification modifiée avec succès")
                else:
                    QMessageBox.warning(self, "Erreur", "Impossible de modifier la planification")
    
    def delete_backup_schedule(self):
        """Supprimer une planification de sauvegarde"""
        selected_items = self.backups_list.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        backup_name = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer la planification '{backup_name}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.manager.remove_backup_schedule(backup_name):
                self.load_data()
                QMessageBox.information(self, "Succès", "Planification supprimée avec succès")
            else:
                QMessageBox.warning(self, "Erreur", "Impossible de supprimer la planification")
    
    def run_selected_backup(self):
        """Exécuter la sauvegarde sélectionnée"""
        selected_items = self.backups_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner une planification")
            return
        
        item = selected_items[0]
        backup_name = item.data(Qt.ItemDataRole.UserRole)
        
        self.progress_label.setText(f"Exécution de la sauvegarde: {backup_name}...")
        self.progress_bar.setValue(0)
        
        # Exécuter dans un thread
        backup_thread = QThread()
        backup_worker = BackupWorker(self.manager)
        backup_worker.moveToThread(backup_thread)
        
        backup_thread.started.connect(lambda: backup_worker.run_backup(backup_name))
        backup_worker.finished.connect(self.on_backup_finished)
        backup_worker.progress.connect(self.on_backup_progress)
        backup_worker.error.connect(self.on_backup_error)
        
        backup_thread.start()
    
    def run_scheduled_backups(self):
        """Exécuter toutes les sauvegardes planifiées"""
        self.progress_label.setText("Exécution des sauvegardes planifiées...")
        self.progress_bar.setValue(0)
        
        # Exécuter dans un thread
        scheduled_thread = QThread()
        scheduled_worker = BackupWorker(self.manager)
        scheduled_worker.moveToThread(scheduled_thread)
        
        scheduled_thread.started.connect(lambda: scheduled_worker.run_scheduled_backups())
        scheduled_worker.finished.connect(self.on_scheduled_backups_finished)
        scheduled_worker.progress.connect(self.on_backup_progress)
        scheduled_worker.error.connect(self.on_backup_error)
        
        scheduled_thread.start()
    
    def check_scheduled_backups(self):
        """Vérifier et exécuter les sauvegardes planifiées"""
        # Cette méthode est appelée par le timer
        # On vérifie si des sauvegardes sont dues
        for backup_name in self.manager.backups.keys():
            if self.manager.is_backup_due(backup_name):
                self.run_selected_backup()
                break  # Exécuter une sauvegarde à la fois
    
    def on_backup_progress(self, message: str):
        """Gérer la progression de la sauvegarde"""
        self.progress_label.setText(message)
        # Mettre à jour la barre de progression (simplifié)
        if "Démarrage" in message:
            self.progress_bar.setValue(10)
        elif "complet" in message.lower():
            self.progress_bar.setValue(100)
        else:
            self.progress_bar.setValue(self.progress_bar.value() + 10)
    
    def on_backup_finished(self, result: BackupResult):
        """Gérer la fin de la sauvegarde"""
        if result.success:
            self.progress_label.setText(f"Sauvegarde terminée: {result.backup_name}")
            self.progress_bar.setValue(100)
            QMessageBox.information(
                self, "Succès",
                f"Sauvegarde réussie:\n\n"
                f"Nom: {result.backup_name}\n"
                f"Base: {result.database_name}\n"
                f"Fichier: {result.file_path}\n"
                f"Taille: {result.file_size} octets\n"
                f"Durée: {result.duration():.2f} secondes"
            )
        else:
            self.on_backup_error(result.error_message, result.backup_name)
        
        # Rafraîchir les données
        self.load_data()
    
    def on_scheduled_backups_finished(self, result: BackupResult):
        """Gérer la fin des sauvegardes planifiées"""
        if result.success:
            self.progress_label.setText("Sauvegardes planifiées terminées")
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Succès", "Toutes les sauvegardes planifiées ont été exécutées")
        else:
            self.on_backup_error(result.error_message, "scheduled")
    
    def on_backup_error(self, error: str, backup_name: str = ""):
        """Gérer les erreurs de sauvegarde"""
        self.progress_label.setText(f"Erreur: {error}")
        self.progress_bar.setValue(0)
        QMessageBox.warning(self, "Erreur", f"Erreur lors de la sauvegarde {backup_name}: {error}")
    
    def on_database_selection_changed(self):
        """Gérer le changement de sélection de base de données"""
        selected_items = self.databases_list.selectedItems()
        if not selected_items:
            self.db_name_label.setText("")
            self.db_type_label.setText("")
            self.db_host_label.setText("")
            self.db_port_label.setText("")
            self.db_username_label.setText("")
            self.db_database_label.setText("")
            return
        
        item = selected_items[0]
        db_name = item.data(Qt.ItemDataRole.UserRole)
        
        if db_name not in self.manager.databases:
            return
        
        config = self.manager.databases[db_name]
        self.db_name_label.setText(config.name)
        self.db_type_label.setText(config.db_type.value)
        self.db_host_label.setText(config.host)
        self.db_port_label.setText(str(config.port) if config.port else "Par défaut")
        self.db_username_label.setText(config.username)
        self.db_database_label.setText(config.database_name)
    
    def on_backup_selection_changed(self):
        """Gérer le changement de sélection de planification"""
        selected_items = self.backups_list.selectedItems()
        if not selected_items:
            self.backup_name_label.setText("")
            self.backup_db_label.setText("")
            self.backup_path_label.setText("")
            self.backup_frequency_label.setText("")
            self.backup_times_label.setText("")
            self.backup_format_label.setText("")
            return
        
        item = selected_items[0]
        backup_name = item.data(Qt.ItemDataRole.UserRole)
        
        if backup_name not in self.manager.backups:
            return
        
        config = self.manager.backups[backup_name]
        self.backup_name_label.setText(config.name)
        self.backup_db_label.setText(config.database_name)
        self.backup_path_label.setText(config.backup_path)
        self.backup_frequency_label.setText(config.frequency.value)
        self.backup_times_label.setText(", ".join(config.schedule_times) if config.schedule_times else "Aucune")
        self.backup_format_label.setText(config.format.value)
    
    def save_settings(self):
        """Sauvegarder les paramètres"""
        # Sauvegarder les paramètres SMTP dans la configuration
        # (À implémenter selon les besoins)
        QMessageBox.information(self, "Succès", "Paramètres sauvegardés")
    
    def show_about(self):
        """Afficher la boîte de dialogue À propos"""
        about_text = """
        <h2>DBBackupManager</h2>
        <p>Gestionnaire de sauvegarde multi-SGBD avec planification flexible</p>
        <p>Version: 1.0.0</p>
        <p>Support: MySQL, MariaDB, PostgreSQL, MSSQL, SQLite</p>
        <p>© 2024 DBBackupManager</p>
        """
        QMessageBox.about(self, "À propos de DBBackupManager", about_text)
    
    def closeEvent(self, event):
        """Gérer la fermeture de la fenêtre"""
        # Arrêter le thread worker
        self.worker_thread.quit()
        self.worker_thread.wait()
        
        # Arrêter le timer
        self.timer.stop()
        
        event.accept()


class QDialog(QDialog):
    """Classe de base pour les dialogues (pour éviter les conflits)"""
    pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Définir le style
    app.setStyle("Fusion")
    
    # Créer et afficher la fenêtre principale
    window = MainWindow()
    window.show()
    
    # Exécuter l'application
    sys.exit(app.exec())
