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
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import get_project_root
PROJECT_ROOT = get_project_root()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit, QListWidget,
    QListWidgetItem, QTabWidget, QGroupBox, QCheckBox, QSpinBox, QTimeEdit,
    QDateEdit, QMessageBox, QInputDialog, QFileDialog, QProgressBar,
    QFormLayout, QFrame, QSplitter, QStatusBar
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
        
        self.name_edit = QLineEdit()
        layout.addRow("Nom:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "MySQL", "MariaDB", "PostgreSQL", "MSSQL", "SQLite"
        ])
        layout.addRow("Type:", self.type_combo)
        
        self.host_edit = QLineEdit("localhost")
        layout.addRow("Hôte:", self.host_edit)
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(0, 65535)
        self.port_spin.setValue(3306)
        layout.addRow("Port:", self.port_spin)
        
        self.username_edit = QLineEdit()
        layout.addRow("Nom d'utilisateur:", self.username_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Mot de passe:", self.password_edit)
        
        self.database_edit = QLineEdit()
        layout.addRow("Nom de la base:", self.database_edit)
        
        self.file_path_edit = QLineEdit()
        self.file_path_button = QPushButton("Parcourir...")
        self.file_path_button.clicked.connect(self.browse_file)
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.file_path_button)
        layout.addRow("Chemin du fichier (SQLite):", file_layout)
        
        self.ssl_check = QCheckBox("Activer SSL")
        layout.addRow(self.ssl_check)
        
        self.ssl_cert_edit = QLineEdit()
        layout.addRow("Certificat SSL:", self.ssl_cert_edit)
        
        self.ssl_key_edit = QLineEdit()
        layout.addRow("Clé SSL:", self.ssl_key_edit)
        
        self.ssl_ca_edit = QLineEdit()
        layout.addRow("CA SSL:", self.ssl_ca_edit)
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setValue(30)
        layout.addRow("Timeout (secondes):", self.timeout_spin)
        
        button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Annuler")
        button_box.addWidget(self.ok_button)
        button_box.addWidget(self.cancel_button)
        layout.addRow(button_box)
        
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        if self.db_config:
            self.load_config()
        
        self.update_ui_for_db_type()
        self.type_combo.currentIndexChanged.connect(self.update_ui_for_db_type)
    
    def update_ui_for_db_type(self):
        db_type = self.type_combo.currentText()
        show_sqlite_fields = db_type == "SQLite"
        self.file_path_edit.setVisible(show_sqlite_fields)
        self.file_path_button.setVisible(show_sqlite_fields)
        
        if db_type in ["MySQL", "MariaDB"]:
            self.port_spin.setValue(3306)
        elif db_type == "PostgreSQL":
            self.port_spin.setValue(5432)
        elif db_type == "MSSQL":
            self.port_spin.setValue(1433)
        elif db_type == "SQLite":
            self.port_spin.setValue(0)
    
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier SQLite", "", "SQLite Files (*.sqlite *.db *.sqlite3)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
    
    def load_config(self):
        if not self.db_config:
            return
        
        self.name_edit.setText(self.db_config.name)
        type_index = self.type_combo.findText(self.db_config.db_type.value.capitalize())
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
        self.setWindowTitle("Ajouter/Modifier une planification")
        self.setMinimumSize(500, 600)
        self.backup_config = backup_config
        self.database_names = database_names or []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.name_edit = QLineEdit()
        layout.addRow("Nom:", self.name_edit)
        
        self.db_combo = QComboBox()
        self.db_combo.addItems(self.database_names)
        layout.addRow("Base de données:", self.db_combo)
        
        self.path_edit = QLineEdit()
        self.path_button = QPushButton("Parcourir...")
        self.path_button.clicked.connect(self.browse_path)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.path_button)
        layout.addRow("Dossier de sauvegarde:", path_layout)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["SQL", "ZIP", "TAR.GZ", "7Z"])
        layout.addRow("Format:", self.format_combo)
        
        self.compression_combo = QComboBox()
        self.compression_combo.addItems(["Aucun", "Faible", "Moyen", "Élevé"])
        layout.addRow("Compression:", self.compression_combo)
        
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems([
            "Horaires", "Quotidienne", "Hebdomadaire", "Mensuelle", "Annuelle", "Personnalisée"
        ])
        self.frequency_combo.currentIndexChanged.connect(self.update_schedule_ui)
        layout.addRow("Fréquence:", self.frequency_combo)
        
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
        
        self.weekdays_group = QGroupBox("Jours de la semaine")
        self.weekdays_layout = QHBoxLayout()
        self.weekday_checks = []
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        for day in days:
            check = QCheckBox(day)
            self.weekday_checks.append(check)
            self.weekdays_layout.addWidget(check)
        self.weekdays_group.setLayout(self.weekdays_layout)
        layout.addRow(self.weekdays_group)
        
        self.monthdays_group = QGroupBox("Jours du mois")
        self.monthdays_layout = QHBoxLayout()
        self.monthday_checks = []
        for i in range(1, 32):
            check = QCheckBox(str(i))
            self.monthday_checks.append(check)
            self.monthdays_layout.addWidget(check)
        self.monthdays_group.setLayout(self.monthdays_layout)
        layout.addRow(self.monthdays_group)
        
        self.months_group = QGroupBox("Mois")
        self.months_layout = QHBoxLayout()
        self.month_checks = []
        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", 
                  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        for month in months:
            check = QCheckBox(month)
            self.month_checks.append(check)
            self.months_layout.addWidget(check)
        self.months_group.setLayout(self.months_layout)
        layout.addRow(self.months_group)
        
        self.prefix_edit = QLineEdit("backup")
        layout.addRow("Préfixe:", self.prefix_edit)
        self.suffix_edit = QLineEdit()
        layout.addRow("Suffixe:", self.suffix_edit)
        self.include_date_check = QCheckBox("Inclure la date")
        self.include_date_check.setChecked(True)
        layout.addRow(self.include_date_check)
        self.encrypt_check = QCheckBox("Chiffrer")
        layout.addRow(self.encrypt_check)
        self.notify_success_check = QCheckBox("Notifier succès")
        self.notify_success_check.setChecked(True)
        layout.addRow(self.notify_success_check)
        self.notify_failure_check = QCheckBox("Notifier échec")
        self.notify_failure_check.setChecked(True)
        layout.addRow(self.notify_failure_check)
        self.email_edit = QLineEdit()
        layout.addRow("Emails:", self.email_edit)
        
        retention_group = QGroupBox("Rétention")
        retention_layout = QGridLayout()
        self.keep_daily_spin = QSpinBox()
        self.keep_daily_spin.setRange(0, 365)
        self.keep_daily_spin.setValue(7)
        retention_layout.addWidget(QLabel("Jours:"), 0, 0)
        retention_layout.addWidget(self.keep_daily_spin, 0, 1)
        self.keep_weekly_spin = QSpinBox()
        self.keep_weekly_spin.setRange(0, 52)
        self.keep_weekly_spin.setValue(4)
        retention_layout.addWidget(QLabel("Semaines:"), 1, 0)
        retention_layout.addWidget(self.keep_weekly_spin, 1, 1)
        self.keep_monthly_spin = QSpinBox()
        self.keep_monthly_spin.setRange(0, 120)
        self.keep_monthly_spin.setValue(12)
        retention_layout.addWidget(QLabel("Mois:"), 2, 0)
        retention_layout.addWidget(self.keep_monthly_spin, 2, 1)
        self.keep_yearly_spin = QSpinBox()
        self.keep_yearly_spin.setRange(0, 100)
        self.keep_yearly_spin.setValue(5)
        retention_layout.addWidget(QLabel("Années:"), 3, 0)
        retention_layout.addWidget(self.keep_yearly_spin, 3, 1)
        retention_group.setLayout(retention_layout)
        layout.addRow(retention_group)
        
        self.pre_command_edit = QLineEdit()
        layout.addRow("Commande pré:", self.pre_command_edit)
        self.post_command_edit = QLineEdit()
        layout.addRow("Commande post:", self.post_command_edit)
        
        button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Annuler")
        button_box.addWidget(self.ok_button)
        button_box.addWidget(self.cancel_button)
        layout.addRow(button_box)
        
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        if self.backup_config:
            self.load_config()
        self.update_schedule_ui()
    
    def update_schedule_ui(self):
        frequency = self.frequency_combo.currentText()
        self.weekdays_group.setVisible(frequency == "Hebdomadaire")
        self.monthdays_group.setVisible(frequency in ["Mensuelle", "Annuelle"])
        self.months_group.setVisible(frequency == "Annuelle")
    
    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if path:
            self.path_edit.setText(path)
    
    def add_time(self):
        time, ok = QInputDialog.getText(self, "Heure", "HH:MM:")
        if ok and time and len(time) == 5 and time[2] == ':':
            try:
                hour, minute = int(time[:2]), int(time[3:])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    self.times_list.addItem(time)
            except ValueError:
                pass
    
    def remove_time(self):
        for item in self.times_list.selectedItems():
            self.times_list.takeItem(self.times_list.row(item))
    
    def load_config(self):
        if not self.backup_config:
            return
        self.name_edit.setText(self.backup_config.name)
        db_index = self.db_combo.findText(self.backup_config.database_name)
        if db_index >= 0:
            self.db_combo.setCurrentIndex(db_index)
        self.path_edit.setText(self.backup_config.backup_path)
        format_index = self.format_combo.findText(self.backup_config.format.value.upper())
        if format_index >= 0:
            self.format_combo.setCurrentIndex(format_index)
        compression_map = {CompressionLevel.NONE: 0, CompressionLevel.LOW: 1, 
                         CompressionLevel.MEDIUM: 2, CompressionLevel.HIGH: 3}
        self.compression_combo.setCurrentIndex(compression_map.get(self.backup_config.compression_level, 2))
        frequency_index = self.frequency_combo.findText(self.backup_config.frequency.value.capitalize())
        if frequency_index >= 0:
            self.frequency_combo.setCurrentIndex(frequency_index)
        for time_str in self.backup_config.schedule_times:
            self.times_list.addItem(time_str)
        for i, check in enumerate(self.weekday_checks):
            check.setChecked(i in self.backup_config.days_of_week)
        for i, check in enumerate(self.monthday_checks):
            check.setChecked((i + 1) in self.backup_config.days_of_month)
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
        self.update_schedule_ui()
    
    def get_config(self) -> BackupConfig:
        format_map = {"SQL": BackupFormat.SQL, "ZIP": BackupFormat.ZIP, 
                     "TAR.GZ": BackupFormat.TAR_GZ, "7Z": BackupFormat.SEVEN_ZIP}
        compression_map = {0: CompressionLevel.NONE, 1: CompressionLevel.LOW,
                         2: CompressionLevel.MEDIUM, 3: CompressionLevel.HIGH}
        frequency_map = {"Horaires": BackupFrequency.HOURLY, "Quotidienne": BackupFrequency.DAILY,
                        "Hebdomadaire": BackupFrequency.WEEKLY, "Mensuelle": BackupFrequency.MONTHLY,
                        "Annuelle": BackupFrequency.YEARLY, "Personnalisée": BackupFrequency.CUSTOM}
        times = [self.times_list.item(i).text() for i in range(self.times_list.count())]
        weekdays = [i for i, check in enumerate(self.weekday_checks) if check.isChecked()]
        monthdays = [i + 1 for i, check in enumerate(self.monthday_checks) if check.isChecked()]
        months = [i + 1 for i, check in enumerate(self.month_checks) if check.isChecked()]
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
            encryption_key="",
            notify_on_success=self.notify_success_check.isChecked(),
            notify_on_failure=self.notify_failure_check.isChecked(),
            email_recipients=emails,
            pre_backup_command=self.pre_command_edit.text().strip(),
            post_backup_command=self.post_command_edit.text().strip()
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DBBackupManager")
        self.setMinimumSize(1024, 768)
        self.manager = BackupManager()
        self.worker_thread = QThread()
        self.worker = BackupWorker(self.manager)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run_scheduled_backups)
        self.worker.finished.connect(self.on_backup_finished)
        self.worker.progress.connect(self.on_backup_progress)
        self.worker.error.connect(self.on_backup_error)
        self.worker_thread.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_scheduled_backups)
        self.timer.start(60000)
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        self.create_menu()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        self.nav_buttons = {
            "databases": QPushButton("Bases de données"),
            "backups": QPushButton("Planifications"),
            "history": QPushButton("Historique"),
            "settings": QPushButton("Paramètres")
        }
        for name, button in self.nav_buttons.items():
            button.setCheckable(True)
            button.setStyleSheet("QPushButton{text-align:left;padding:8px;border:none;background:transparent;}QPushButton:checked{background:#e0e0e0;border-left:3px solid #0078d7;}")
            button.clicked.connect(lambda checked, n=name: self.show_page(n))
            left_layout.addWidget(button)
        self.nav_buttons["databases"].setChecked(True)
        
        self.right_panel = QTabWidget()
        self.pages = {
            "databases": self.create_databases_page(),
            "backups": self.create_backups_page(),
            "history": self.create_history_page(),
            "settings": self.create_settings_page()
        }
        for name, page in self.pages.items():
            self.right_panel.addTab(page, name.capitalize())
        
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.create_toolbar()
    
    def create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Fichier")
        file_menu.addAction("Nouvelle BD", self.add_database)
        file_menu.addAction("Nouvelle planification", self.add_backup_schedule)
        file_menu.addSeparator()
        file_menu.addAction("Quitter", self.close)
        tools_menu = menubar.addMenu("Outils")
        tools_menu.addAction("Exécuter planifiées", self.run_scheduled_backups)
        help_menu = menubar.addMenu("Aide")
        help_menu.addAction("À propos", self.show_about)
    
    def create_toolbar(self):
        toolbar = self.addToolBar("Barre d'outils")
        toolbar.addAction("Exécuter", self.run_selected_backup)
        toolbar.addAction("Tester", self.test_selected_connection)
        toolbar.addSeparator()
        toolbar.addAction("Rafraîchir", self.load_data)
    
    def create_databases_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QPushButton("Ajouter", clicked=self.add_database))
        toolbar.addWidget(QPushButton("Modifier", clicked=self.edit_database))
        toolbar.addWidget(QPushButton("Supprimer", clicked=self.delete_database))
        toolbar.addWidget(QPushButton("Tester", clicked=self.test_selected_connection))
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.databases_list = QListWidget()
        self.databases_list.itemDoubleClicked.connect(self.edit_database)
        self.databases_list.itemSelectionChanged.connect(self.on_database_selection_changed)
        layout.addWidget(self.databases_list)
        self.db_details_group = QGroupBox("Détails")
        self.db_details_layout = QFormLayout()
        self.db_name_label = QLabel()
        self.db_type_label = QLabel()
        self.db_host_label = QLabel()
        self.db_port_label = QLabel()
        self.db_username_label = QLabel()
        self.db_database_label = QLabel()
        for label, name in [(self.db_name_label, "Nom"), (self.db_type_label, "Type"), 
                           (self.db_host_label, "Hôte"), (self.db_port_label, "Port"),
                           (self.db_username_label, "Utilisateur"), (self.db_database_label, "Base")]:
            self.db_details_layout.addRow(f"{name}:", label)
        self.db_details_group.setLayout(self.db_details_layout)
        layout.addWidget(self.db_details_group)
        return page
    
    def create_backups_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QPushButton("Ajouter", clicked=self.add_backup_schedule))
        toolbar.addWidget(QPushButton("Modifier", clicked=self.edit_backup_schedule))
        toolbar.addWidget(QPushButton("Supprimer", clicked=self.delete_backup_schedule))
        toolbar.addWidget(QPushButton("Exécuter", clicked=self.run_selected_backup))
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.backups_list = QListWidget()
        self.backups_list.itemDoubleClicked.connect(self.edit_backup_schedule)
        self.backups_list.itemSelectionChanged.connect(self.on_backup_selection_changed)
        layout.addWidget(self.backups_list)
        self.backup_details_group = QGroupBox("Détails")
        self.backup_details_layout = QFormLayout()
        self.backup_name_label = QLabel()
        self.backup_db_label = QLabel()
        self.backup_path_label = QLabel()
        self.backup_frequency_label = QLabel()
        self.backup_times_label = QLabel()
        self.backup_format_label = QLabel()
        for label, name in [(self.backup_name_label, "Nom"), (self.backup_db_label, "Base"),
                           (self.backup_path_label, "Dossier"), (self.backup_frequency_label, "Fréquence"),
                           (self.backup_times_label, "Heures"), (self.backup_format_label, "Format")]:
            self.backup_details_layout.addRow(f"{name}:", label)
        self.backup_details_group.setLayout(self.backup_details_layout)
        layout.addWidget(self.backup_details_group)
        self.progress_group = QGroupBox("Progression")
        self.progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_label = QLabel("Prêt")
        self.progress_layout.addWidget(self.progress_bar)
        self.progress_layout.addWidget(self.progress_label)
        self.progress_group.setLayout(self.progress_layout)
        layout.addWidget(self.progress_group)
        return page
    
    def create_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        return page
    
    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        return page
    
    def load_data(self):
        self.databases_list.clear()
        for name, config in self.manager.databases.items():
            item = QListWidgetItem(f"{name} ({config.db_type.value})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.databases_list.addItem(item)
        self.backups_list.clear()
        for name, config in self.manager.backups.items():
            item = QListWidgetItem(f"{name} - {config.database_name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.backups_list.addItem(item)
    
    def show_page(self, page_name):
        for button in self.nav_buttons.values():
            button.setChecked(False)
        if page_name in self.nav_buttons:
            self.nav_buttons[page_name].setChecked(True)
        self.right_panel.setCurrentIndex(list(self.pages.keys()).index(page_name))
    
    def add_database(self):
        dialog = DatabaseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            if config.name:
                if self.manager.add_database(config):
                    self.load_data()
                    QMessageBox.information(self, "Succès", "Base ajoutée")
                else:
                    QMessageBox.warning(self, "Erreur", "Nom existe déjà")
    
    def edit_database(self):
        selected = self.databases_list.selectedItems()
        if selected:
            db_name = selected[0].data(Qt.ItemDataRole.UserRole)
            if db_name in self.manager.databases:
                dialog = DatabaseDialog(self, self.manager.databases[db_name])
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    new_config = dialog.get_config()
                    if new_config.name:
                        if self.manager.update_database(db_name, new_config):
                            self.load_data()
                            QMessageBox.information(self, "Succès", "Base modifiée")
    
    def delete_database(self):
        selected = self.databases_list.selectedItems()
        if selected:
            db_name = selected[0].data(Qt.ItemDataRole.UserRole)
            if QMessageBox.question(self, "Confirmation", f"Supprimer {db_name}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                if self.manager.remove_database(db_name):
                    self.load_data()
                    QMessageBox.information(self, "Succès", "Base supprimée")
    
    def test_selected_connection(self):
        selected = self.databases_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Erreur", "Sélectionnez une base")
            return
        db_name = selected[0].data(Qt.ItemDataRole.UserRole)
        self.progress_label.setText(f"Test {db_name}...")
        test_thread = QThread()
        test_worker = BackupWorker(self.manager)
        test_worker.moveToThread(test_thread)
        test_thread.started.connect(lambda: test_worker.test_connection(db_name))
        test_worker.finished.connect(lambda r: self.on_test_finished(r, db_name))
        test_worker.error.connect(lambda e: self.on_test_error(e, db_name))
        test_thread.start()
    
    def on_test_finished(self, result, db_name):
        if result.success:
            self.progress_label.setText(f"OK: {db_name}")
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Succès", f"Connexion OK: {db_name}")
        else:
            self.on_test_error(result.error_message, db_name)
    
    def on_test_error(self, error, db_name):
        self.progress_label.setText(f"Erreur: {db_name}")
        self.progress_bar.setValue(0)
        QMessageBox.warning(self, "Erreur", f"Connexion échouée: {error}")
    
    def add_backup_schedule(self):
        if not self.manager.databases:
            QMessageBox.warning(self, "Erreur", "Ajoutez une base d'abord")
            return
        dialog = BackupScheduleDialog(self, database_names=list(self.manager.databases.keys()))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            if config.name:
                if self.manager.add_backup_schedule(config):
                    self.load_data()
                    QMessageBox.information(self, "Succès", "Planification ajoutée")
    
    def edit_backup_schedule(self):
        selected = self.backups_list.selectedItems()
        if selected:
            backup_name = selected[0].data(Qt.ItemDataRole.UserRole)
            if backup_name in self.manager.backups:
                dialog = BackupScheduleDialog(self, self.manager.backups[backup_name], list(self.manager.databases.keys()))
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    new_config = dialog.get_config()
                    if new_config.name:
                        if self.manager.update_backup_schedule(backup_name, new_config):
                            self.load_data()
                            QMessageBox.information(self, "Succès", "Planification modifiée")
    
    def delete_backup_schedule(self):
        selected = self.backups_list.selectedItems()
        if selected:
            backup_name = selected[0].data(Qt.ItemDataRole.UserRole)
            if QMessageBox.question(self, "Confirmation", f"Supprimer {backup_name}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                if self.manager.remove_backup_schedule(backup_name):
                    self.load_data()
                    QMessageBox.information(self, "Succès", "Planification supprimée")
    
    def run_selected_backup(self):
        selected = self.backups_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Erreur", "Sélectionnez une planification")
            return
        backup_name = selected[0].data(Qt.ItemDataRole.UserRole)
        self.progress_label.setText(f"Exécution: {backup_name}...")
        self.progress_bar.setValue(0)
        backup_thread = QThread()
        backup_worker = BackupWorker(self.manager)
        backup_worker.moveToThread(backup_thread)
        backup_thread.started.connect(lambda: backup_worker.run_backup(backup_name))
        backup_worker.finished.connect(self.on_backup_finished)
        backup_worker.progress.connect(self.on_backup_progress)
        backup_worker.error.connect(self.on_backup_error)
        backup_thread.start()
    
    def run_scheduled_backups(self):
        self.progress_label.setText("Exécution planifiée...")
        self.progress_bar.setValue(0)
        scheduled_thread = QThread()
        scheduled_worker = BackupWorker(self.manager)
        scheduled_worker.moveToThread(scheduled_thread)
        scheduled_thread.started.connect(lambda: scheduled_worker.run_scheduled_backups())
        scheduled_worker.finished.connect(self.on_scheduled_backups_finished)
        scheduled_worker.progress.connect(self.on_backup_progress)
        scheduled_worker.error.connect(self.on_backup_error)
        scheduled_thread.start()
    
    def check_scheduled_backups(self):
        for backup_name in self.manager.backups.keys():
            if self.manager.is_backup_due(backup_name):
                self.run_selected_backup()
                break
    
    def on_backup_progress(self, message):
        self.progress_label.setText(message)
        if "Démarrage" in message:
            self.progress_bar.setValue(10)
        elif "complet" in message.lower():
            self.progress_bar.setValue(100)
        else:
            self.progress_bar.setValue(self.progress_bar.value() + 10)
    
    def on_backup_finished(self, result):
        if result.success:
            self.progress_label.setText(f"Terminé: {result.backup_name}")
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Succès", f"Sauvegarde OK: {result.backup_name}")
        else:
            self.on_backup_error(result.error_message, result.backup_name)
        self.load_data()
    
    def on_scheduled_backups_finished(self, result):
        if result.success:
            self.progress_label.setText("Planifiées terminées")
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Succès", "Toutes les sauvegardes exécutées")
        else:
            self.on_backup_error(result.error_message, "scheduled")
    
    def on_backup_error(self, error, backup_name=""):
        self.progress_label.setText(f"Erreur: {error}")
        self.progress_bar.setValue(0)
        QMessageBox.warning(self, "Erreur", f"Échec: {error}")
    
    def on_database_selection_changed(self):
        selected = self.databases_list.selectedItems()
        if not selected:
            for label in [self.db_name_label, self.db_type_label, self.db_host_label, self.db_port_label, self.db_username_label, self.db_database_label]:
                label.setText("")
            return
        db_name = selected[0].data(Qt.ItemDataRole.UserRole)
        if db_name in self.manager.databases:
            config = self.manager.databases[db_name]
            self.db_name_label.setText(config.name)
            self.db_type_label.setText(config.db_type.value)
            self.db_host_label.setText(config.host)
            self.db_port_label.setText(str(config.port) if config.port else "Par défaut")
            self.db_username_label.setText(config.username)
            self.db_database_label.setText(config.database_name)
    
    def on_backup_selection_changed(self):
        selected = self.backups_list.selectedItems()
        if not selected:
            for label in [self.backup_name_label, self.backup_db_label, self.backup_path_label, self.backup_frequency_label, self.backup_times_label, self.backup_format_label]:
                label.setText("")
            return
        backup_name = selected[0].data(Qt.ItemDataRole.UserRole)
        if backup_name in self.manager.backups:
            config = self.manager.backups[backup_name]
            self.backup_name_label.setText(config.name)
            self.backup_db_label.setText(config.database_name)
            self.backup_path_label.setText(config.backup_path)
            self.backup_frequency_label.setText(config.frequency.value)
            self.backup_times_label.setText(", ".join(config.schedule_times) if config.schedule_times else "Aucune")
            self.backup_format_label.setText(config.format.value)
    
    def save_settings(self):
        QMessageBox.information(self, "Succès", "Paramètres sauvegardés")
    
    def show_about(self):
        QMessageBox.about(self, "À propos", "DBBackupManager v1.0\nGestionnaire de sauvegarde multi-SGBD")
    
    def closeEvent(self, event):
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
