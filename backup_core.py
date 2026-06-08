import os
import subprocess
import datetime
import shutil
import logging
from pathlib import Path

# Configurer les logs
logging.basicConfig(
    filename='backup_manager.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_backup(db_type, host, port, user, password, db_name, backup_dir):
    """Exécute une sauvegarde pour la base de données spécifiée."""
    try:
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if db_type == "SQLite":
            # Pour SQLite, "host" contient généralement le chemin du fichier .db
            source_file = host
            if not os.path.exists(source_file):
                raise FileNotFoundError(f"Fichier SQLite introuvable: {source_file}")

            filename = f"sqlite_backup_{timestamp}.db"
            dest_file = os.path.join(backup_dir, filename)
            shutil.copy2(source_file, dest_file)
            logging.info(f"Sauvegarde SQLite réussie: {dest_file}")
            return True, f"Succès: {dest_file}"

        elif db_type == "MySQL":
            filename = f"{db_name}_mysql_{timestamp}.sql"
            filepath = os.path.join(backup_dir, filename)

            # Utilisation de mysqldump
            os.environ["MYSQL_PWD"] = password
            cmd = [
                "mysqldump",
                "-h", host,
                "-P", str(port),
                "-u", user,
                db_name
            ]

            with open(filepath, "w") as outfile:
                result = subprocess.run(cmd, stdout=outfile, stderr=subprocess.PIPE, text=True)

            if result.returncode == 0:
                logging.info(f"Sauvegarde MySQL réussie: {filepath}")
                return True, f"Succès: {filepath}"
            else:
                if os.path.exists(filepath):
                    os.remove(filepath)
                logging.error(f"Erreur mysqldump: {result.stderr}")
                return False, f"Erreur MySQL: {result.stderr}"

        elif db_type == "PostgreSQL":
            filename = f"{db_name}_pg_{timestamp}.sql"
            filepath = os.path.join(backup_dir, filename)

            # Utilisation de pg_dump
            os.environ["PGPASSWORD"] = password
            cmd = [
                "pg_dump",
                "-h", host,
                "-p", str(port),
                "-U", user,
                "-d", db_name,
                "-F", "p" # Format texte pur (SQL)
            ]

            with open(filepath, "w") as outfile:
                result = subprocess.run(cmd, stdout=outfile, stderr=subprocess.PIPE, text=True)

            if result.returncode == 0:
                logging.info(f"Sauvegarde PostgreSQL réussie: {filepath}")
                return True, f"Succès: {filepath}"
            else:
                if os.path.exists(filepath):
                    os.remove(filepath)
                logging.error(f"Erreur pg_dump: {result.stderr}")
                return False, f"Erreur PostgreSQL: {result.stderr}"

        elif db_type == "MSSQL":
            filename = f"{db_name}_mssql_{timestamp}.bak"
            filepath = os.path.join(backup_dir, filename)

            # Utilisation de sqlcmd pour MSSQL
            # La commande SQL effectue un BACKUP DATABASE
            sql_query = f"BACKUP DATABASE [{db_name}] TO DISK = N'{filepath}' WITH NOFORMAT, NOINIT, NAME = N'{db_name}-Full Database Backup', SKIP, NOREWIND, NOUNLOAD, STATS = 10"

            cmd = [
                "sqlcmd",
                "-S", f"{host},{port}" if port else host,
                "-U", user,
                "-P", password,
                "-Q", sql_query
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0 and not "Msg " in result.stderr:
                logging.info(f"Sauvegarde MSSQL réussie: {filepath}")
                return True, f"Succès: {filepath}"
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                logging.error(f"Erreur sqlcmd: {error_msg}")
                return False, f"Erreur MSSQL: {error_msg}"

        else:
            return False, f"Type de base de données non supporté: {db_type}"

    except Exception as e:
        logging.error(f"Erreur inattendue: {str(e)}")
        return False, f"Erreur: {str(e)}"
