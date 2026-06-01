# DBBackupManager

**Gestionnaire de sauvegarde multi-SGBD avec planification flexible**

DBBackupManager est un logiciel complet pour la sauvegarde automatique de bases de données SQL (MySQL, MariaDB, PostgreSQL, MSSQL, SQLite) avec une planification configurable en jour, semaine, mois et année.

## 📋 Fonctionnalités

### ✅ Support Multi-SGBD
- **MySQL** / **MariaDB** - Utilise `mysqldump` pour des sauvegardes SQL complètes
- **PostgreSQL** - Utilise `pg_dump` pour des sauvegardes fiables
- **Microsoft SQL Server** - Support via `sqlcmd` ou `pyodbc`
- **SQLite** - Sauvegarde par copie de fichier

### ✅ Planification Flexible
- **Horaires** - Exécution à des heures spécifiques chaque heure
- **Quotidienne** - Sauvegardes quotidiennes à des heures précises
- **Hebdomadaire** - Sauvegardes les jours sélectionnés de la semaine
- **Mensuelle** - Sauvegardes les jours spécifiques du mois
- **Annuelle** - Sauvegardes aux dates annuelles
- **Personnalisée** - Configuration avancée selon vos besoins

### ✅ Gestion des sauvegardes
- **Compression** - ZIP, TAR.GZ, 7Z avec niveaux de compression configurables
- **Chiffrement** - Chiffrement AES des fichiers de sauvegarde
- **Rétention automatique** - Suppression des anciennes sauvegardes selon des règles configurables
- **Vérification d'intégrité** - Calcul de checksum MD5 pour chaque sauvegarde
- **Notifications** - Alertes par email en cas de succès ou d'échec

### ✅ Interface Utilisateur
- **Interface Graphique (GUI)** - Application PyQt6 moderne et intuitive
- **Interface Ligne de Commande (CLI)** - Puissante et scriptable
- **Journalisation complète** - Historique détaillé de toutes les opérations

## 📦 Installation

### Prérequis

#### Système
- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)

#### Dépendances système (selon le SGBD)
- **MySQL/MariaDB**: `mysqldump` et `mysql` doivent être dans le PATH
- **PostgreSQL**: `pg_dump` et `psql` doivent être dans le PATH
- **MSSQL**: `sqlcmd` ou `pyodbc` avec le pilote ODBC

#### Installation sur Linux (Debian/Ubuntu)
```bash
# Installer les dépendances système
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Pour MySQL
sudo apt install -y mysql-client

# Pour PostgreSQL
sudo apt install -y postgresql-client

# Pour MSSQL (optionnel)
sudo apt install -y unixodbc unixodbc-dev

# Créer un environnement virtuel
python3 -m venv dbbackup-venv
source dbbackup-venv/bin/activate

# Installer les dépendances Python
pip install -r requirements.txt
```

#### Installation sur Windows
```cmd
# Créer un environnement virtuel
python -m venv dbbackup-venv
.\dbbackup-venv\Scripts\activate

# Installer les dépendances Python
pip install -r requirements.txt

# Pour MySQL: Installer MySQL Server ou MySQL Workbench
# Pour PostgreSQL: Installer PostgreSQL
# Pour MSSQL: Installer SQL Server et les outils clients
```

## 🚀 Utilisation

### Interface Graphique

```bash
# Démarrer l'interface graphique
python gui/backup_gui.py
```

L'interface graphique offre :
- Gestion visuelle des bases de données
- Configuration des planifications avec calendrier
- Exécution manuelle des sauvegardes
- Visualisation de l'historique
- Configuration des notifications

### Interface Ligne de Commande

#### Configuration initiale
```bash
# Initialiser la configuration
python cli/backup_cli.py config init

# Afficher la configuration actuelle
python cli/backup_cli.py config show
```

#### Gestion des bases de données
```bash
# Ajouter une base de données MySQL
python cli/backup_cli.py db add --name mysql_prod \
  --type mysql \
  --host db.example.com \
  --port 3306 \
  --user dbuser \
  --password dbpassword \
  --database production_db

# Lister les bases de données
python cli/backup_cli.py db list

# Lister les bases de données disponibles sur un serveur
python cli/backup_cli.py db list-databases --name mysql_prod

# Tester une connexion
python cli/backup_cli.py db test --name mysql_prod

# Modifier une base de données
python cli/backup_cli.py db update --name mysql_prod --password newpassword

# Supprimer une base de données
python cli/backup_cli.py db remove --name mysql_prod
```

#### Gestion des sauvegardes
```bash
# Ajouter une planification quotidienne
python cli/backup_cli.py backup add \
  --name daily_mysql \
  --database mysql_prod \
  --path /backups/mysql \
  --frequency daily \
  --times "02:00" "14:00" \
  --format zip \
  --compression high \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 12

# Ajouter une planification hebdomadaire (le lundi à 3h)
python cli/backup_cli.py backup add \
  --name weekly_postgres \
  --database postgres_prod \
  --path /backups/postgres \
  --frequency weekly \
  --times "03:00" \
  --days 0 \
  --format tar.gz

# Ajouter une planification mensuelle (le 1er du mois)
python cli/backup_cli.py backup add \
  --name monthly_backup \
  --database mysql_prod \
  --path /backups/monthly \
  --frequency monthly \
  --times "01:00" \
  --month-days 1

# Ajouter une planification annuelle (le 1er janvier)
python cli/backup_cli.py backup add \
  --name yearly_backup \
  --database mysql_prod \
  --path /backups/yearly \
  --frequency yearly \
  --times "00:00" \
  --months 1 \
  --month-days 1

# Lister les planifications
python cli/backup_cli.py backup list

# Exécuter une sauvegarde manuellement
python cli/backup_cli.py backup run --name daily_mysql

# Exécuter toutes les sauvegardes planifiées
python cli/backup_cli.py backup run-all

# Vérifier et exécuter les sauvegardes dues
python cli/backup_cli.py schedule check
```

#### Restauration
```bash
# Restaurer une sauvegarde
python cli/backup_cli.py restore \
  --backup /backups/mysql/production_db_20240101_020000.sql \
  --database mysql_prod
```

## 📁 Structure du projet

```
DBBackupManager/
├── db_backup_manager.py      # Module principal de sauvegarde
├── cli/
│   └── backup_cli.py         # Interface ligne de commande
├── gui/
│   └── backup_gui.py         # Interface graphique
├── config/
│   ├── config.json           # Configuration des bases de données
│   └── schedules.json        # Configuration des planifications
├── backups/                  # Dossier des sauvegardes (créé automatiquement)
├── logs/                     # Journaux d'exécution
├── requirements.txt          # Dépendances Python
└── README.md                 # Documentation
```

## 🔧 Configuration

### Fichier config.json

```json
{
  "databases": {
    "nom_base": {
      "name": "nom_base",
      "db_type": "mysql|mariadb|postgresql|mssql|sqlite",
      "host": "localhost",
      "port": 3306,
      "username": "utilisateur",
      "password": "motdepasse",
      "database_name": "nom_bdd",
      "file_path": "",
      "ssl_enabled": false,
      "ssl_cert": "",
      "ssl_key": "",
      "ssl_ca": "",
      "timeout": 30
    }
  }
}
```

### Fichier schedules.json

```json
{
  "backups": {
    "nom_sauvegarde": {
      "name": "nom_sauvegarde",
      "database_name": "nom_base",
      "backup_path": "./backups",
      "format": "sql|zip|tar.gz|7z",
      "compression_level": 0-9,
      "frequency": "hourly|daily|weekly|monthly|yearly|custom",
      "schedule_times": ["HH:MM"],
      "days_of_week": [0-6],
      "days_of_month": [1-31],
      "months": [1-12],
      "keep_daily": 7,
      "keep_weekly": 4,
      "keep_monthly": 12,
      "keep_yearly": 5,
      "include_date_in_filename": true,
      "filename_prefix": "backup",
      "filename_suffix": "",
      "encrypt": false,
      "encryption_key": "",
      "notify_on_success": true,
      "notify_on_failure": true,
      "email_recipients": ["email@example.com"],
      "pre_backup_command": "",
      "post_backup_command": ""
    }
  }
}
```

## 🎯 Exemples de configuration

### Exemple 1: Sauvegarde quotidienne avec compression
```bash
python cli/backup_cli.py backup add \
  --name daily_backup \
  --database mysql_prod \
  --path /backups/daily \
  --frequency daily \
  --times "02:00" \
  --format zip \
  --compression high \
  --keep-daily 30
```

### Exemple 2: Sauvegarde hebdomadaire avec chiffrement
```bash
python cli/backup_cli.py backup add \
  --name weekly_secure \
  --database postgres_prod \
  --path /backups/weekly \
  --frequency weekly \
  --times "03:00" \
  --days 0 6 \
  --format zip \
  --encrypt \
  --notify-success \
  --email admin@example.com
```

### Exemple 3: Sauvegarde mensuelle avec rétention longue
```bash
python cli/backup_cli.py backup add \
  --name monthly_archive \
  --database mysql_prod \
  --path /backups/monthly \
  --frequency monthly \
  --times "01:00" \
  --month-days 1 \
  --format tar.gz \
  --keep-monthly 24 \
  --keep-yearly 10
```

## 🔒 Sécurité

### Chiffrement
- Les sauvegardes peuvent être chiffrées avec AES-256
- La clé de chiffrement est stockée dans la configuration
- Assurez-vous de sauvegarder votre clé de chiffrement en lieu sûr

### Bonnes pratiques
1. **Stockage sécurisé** : Conservez les fichiers de configuration dans un endroit sécurisé
2. **Permissions** : Limitez les permissions d'accès aux fichiers de sauvegarde
3. **Mots de passe** : Utilisez des mots de passe forts pour les bases de données
4. **SSL** : Activez SSL pour les connexions aux bases de données
5. **Sauvegarde des clés** : Sauvegardez vos clés de chiffrement séparément

## 📊 Surveillance et maintenance

### Vérification des sauvegardes
```bash
# Vérifier quelles sauvegardes sont dues
python cli/backup_cli.py schedule check

# Afficher l'historique des sauvegardes
python cli/backup_cli.py schedule list
```

### Nettoyage
- La politique de rétention est appliquée automatiquement après chaque sauvegarde
- Les anciennes sauvegardes sont supprimées selon les règles configurées

### Journalisation
- Tous les événements sont journalisés dans `logs/backup_manager.log`
- Les erreurs sont également affichées dans la console

## 🛠️ Dépannage

### Problèmes courants

#### Erreur: "mysqldump command not found"
**Solution**: Installez MySQL client ou ajoutez le chemin de mysqldump au PATH

#### Erreur: "pg_dump command not found"
**Solution**: Installez PostgreSQL client ou ajoutez le chemin de pg_dump au PATH

#### Erreur: "Connection failed"
**Solution**: Vérifiez les informations de connexion (hôte, port, utilisateur, mot de passe)

#### Erreur: "Database not found"
**Solution**: Vérifiez que le nom de la base de données est correct

#### Erreur: "Permission denied"
**Solution**: Vérifiez les permissions sur le dossier de sauvegarde

### Niveau de logging
Pour augmenter le niveau de détail des logs :
```python
# Dans db_backup_manager.py, modifiez le niveau du logger
logger.setLevel(logging.DEBUG)
```

## 📝 Journal des modifications

### Version 1.0.0
- Première version stable
- Support complet de MySQL, MariaDB, PostgreSQL, MSSQL, SQLite
- Interface graphique et ligne de commande
- Planification flexible
- Compression et chiffrement
- Notifications par email
- Politique de rétention

## 🤝 Contribution

Les contributions sont les bienvenues !

1. Fork le projet
2. Créez une branche de fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. Commitez vos modifications (`git commit -m 'Add some AmazingFeature'`)
4. Poussez vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

## 📄 Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- À tous les contributeurs
- À la communauté open source
- Aux développeurs des bibliothèques utilisées

---

**DBBackupManager** - Votre solution complète de sauvegarde de bases de données

Pour plus d'informations, consultez la documentation ou contactez l'équipe de développement.
