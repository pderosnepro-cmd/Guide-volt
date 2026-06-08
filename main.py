import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import schedule
import json
import os
from backup_core import run_backup, test_connection, discover_local_instances

CONFIG_FILE = "backup_config.json"

class BackupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Easy DB Backup Manager")
        self.root.geometry("600x700")

        self.jobs = []
        self.is_running = False
        self.daemon_thread = None

        self.create_widgets()
        self.load_config()

    def create_widgets(self):
        # --- Section Configuration Base de données ---
        db_frame = ttk.LabelFrame(self.root, text="Configuration Base de Données", padding=10)
        db_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(db_frame, text="Type:").grid(row=0, column=0, sticky="w")
        self.db_type_var = tk.StringVar(value="MySQL")
        self.db_type_cb = ttk.Combobox(db_frame, textvariable=self.db_type_var, values=["MySQL", "PostgreSQL", "MSSQL", "SQLite"])
        self.db_type_cb.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.db_type_cb.bind("<<ComboboxSelected>>", self.on_db_type_change)

        ttk.Label(db_frame, text="Hôte / Chemin (SQLite):").grid(row=1, column=0, sticky="w")
        self.host_entry = ttk.Entry(db_frame)
        self.host_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.host_entry.insert(0, "localhost")

        ttk.Label(db_frame, text="Port:").grid(row=2, column=0, sticky="w")
        self.port_entry = ttk.Entry(db_frame)
        self.port_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.port_entry.insert(0, "3306")

        ttk.Label(db_frame, text="Utilisateur:").grid(row=3, column=0, sticky="w")
        self.user_entry = ttk.Entry(db_frame)
        self.user_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=2)
        self.user_entry.insert(0, "root")

        ttk.Label(db_frame, text="Mot de passe:").grid(row=4, column=0, sticky="w")
        self.pass_entry = ttk.Entry(db_frame, show="*")
        self.pass_entry.grid(row=4, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(db_frame, text="Nom Base:").grid(row=5, column=0, sticky="w")
        self.dbname_entry = ttk.Entry(db_frame)
        self.dbname_entry.grid(row=5, column=1, sticky="ew", padx=5, pady=2)

        # Outils Base de données
        db_tools_frame = ttk.Frame(db_frame)
        db_tools_frame.grid(row=6, column=0, columnspan=2, pady=10)
        ttk.Button(db_tools_frame, text="🔍 Chercher Instances Locales", command=self.find_instances).pack(side="left", padx=5)
        ttk.Button(db_tools_frame, text="⚡ Tester Connexion", command=self.test_conn).pack(side="left", padx=5)

        # --- Section Répertoire ---
        dir_frame = ttk.LabelFrame(self.root, text="Dossier de Sauvegarde", padding=10)
        dir_frame.pack(fill="x", padx=10, pady=5)

        self.dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.dir_var, state="readonly").pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(dir_frame, text="Parcourir", command=self.browse_dir).pack(side="right")

        # --- Section Planification ---
        sched_frame = ttk.LabelFrame(self.root, text="Planification", padding=10)
        sched_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(sched_frame, text="Fréquence:").grid(row=0, column=0, sticky="w")
        self.freq_var = tk.StringVar(value="Quotidien")
        ttk.Combobox(sched_frame, textvariable=self.freq_var, values=["Horaire", "Quotidien"]).grid(row=0, column=1, padx=5)

        ttk.Label(sched_frame, text="Heure (HH:MM) si Quotidien:").grid(row=0, column=2, sticky="w")
        self.time_entry = ttk.Entry(sched_frame, width=10)
        self.time_entry.grid(row=0, column=3, padx=5)
        self.time_entry.insert(0, "02:00")

        # --- Boutons d'Action ---
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(btn_frame, text="Ajouter Planification", command=self.add_job).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Tester Sauvegarde Immédiate", command=self.test_backup).pack(side="left", padx=5)
        self.toggle_btn = ttk.Button(btn_frame, text="Démarrer Planificateur", command=self.toggle_scheduler)
        self.toggle_btn.pack(side="right", padx=5)

        # --- Liste des Tâches ---
        list_frame = ttk.LabelFrame(self.root, text="Tâches Planifiées", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.job_listbox = tk.Listbox(list_frame)
        self.job_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.job_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.job_listbox.config(yscrollcommand=scrollbar.set)

        ttk.Button(self.root, text="Supprimer la tâche sélectionnée", command=self.remove_job).pack(pady=5)

    def on_db_type_change(self, event=None):
        db_type = self.db_type_var.get()
        self.port_entry.delete(0, tk.END)
        if db_type == "MySQL":
            self.port_entry.insert(0, "3306")
        elif db_type == "PostgreSQL":
            self.port_entry.insert(0, "5432")
        elif db_type == "MSSQL":
            self.port_entry.insert(0, "1433")

    def find_instances(self):
        self.root.config(cursor="wait")
        self.root.update()
        instances = discover_local_instances()
        self.root.config(cursor="")

        if not instances:
            messagebox.showinfo("Résultat", "Aucune instance locale trouvée sur les ports standards.")
            return

        win = tk.Toplevel(self.root)
        win.title("Instances Locales")
        ttk.Label(win, text="Instances détectées sur ce PC :", padding=10).pack()

        listbox = tk.Listbox(win, width=50)
        listbox.pack(padx=10, pady=5)

        for name, port in instances:
            listbox.insert(tk.END, f"{name} (Port: {port})")

        def on_select():
            sel = listbox.curselection()
            if sel:
                name, port = instances[sel[0]]
                if "MySQL" in name:
                    self.db_type_var.set("MySQL")
                    self.host_entry.delete(0, tk.END)
                    self.host_entry.insert(0, "127.0.0.1")
                    self.port_entry.delete(0, tk.END)
                    self.port_entry.insert(0, str(port))
                elif "PostgreSQL" in name:
                    self.db_type_var.set("PostgreSQL")
                    self.host_entry.delete(0, tk.END)
                    self.host_entry.insert(0, "127.0.0.1")
                    self.port_entry.delete(0, tk.END)
                    self.port_entry.insert(0, str(port))
                elif "MSSQL" in name:
                    self.db_type_var.set("MSSQL")
                    if port == "Dynamique":
                        # Extraire le nom de l'instance "MSSQL (NOM_INSTANCE)"
                        instance_name = name.replace("MSSQL (", "").replace(")", "")
                        self.host_entry.delete(0, tk.END)
                        self.host_entry.insert(0, instance_name)
                        self.port_entry.delete(0, tk.END)
                    else:
                        self.host_entry.delete(0, tk.END)
                        self.host_entry.insert(0, "127.0.0.1")
                        self.port_entry.delete(0, tk.END)
                        self.port_entry.insert(0, "1433")

                win.destroy()

        ttk.Button(win, text="Utiliser cette instance", command=on_select).pack(pady=10)

    def test_conn(self):
        self.root.config(cursor="wait")
        self.root.update()

        success, msg = test_connection(
            self.db_type_var.get(),
            self.host_entry.get(),
            self.port_entry.get(),
            self.user_entry.get(),
            self.pass_entry.get(),
            self.dbname_entry.get()
        )
        self.root.config(cursor="")

        if success:
            messagebox.showinfo("Succès", msg)
        else:
            messagebox.showerror("Erreur", msg)

    def browse_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_var.set(directory)

    def test_backup(self):
        if not self.validate_inputs(): return

        self.root.config(cursor="wait")
        self.root.update()

        success, msg = run_backup(
            self.db_type_var.get(),
            self.host_entry.get(),
            self.port_entry.get(),
            self.user_entry.get(),
            self.pass_entry.get(),
            self.dbname_entry.get(),
            self.dir_var.get()
        )

        self.root.config(cursor="")

        if success:
            messagebox.showinfo("Succès", msg)
        else:
            messagebox.showerror("Erreur", msg)

    def validate_inputs(self):
        if not self.dir_var.get():
            messagebox.showwarning("Attention", "Veuillez choisir un répertoire de sauvegarde.")
            return False
        if not self.dbname_entry.get() and self.db_type_var.get() != "SQLite":
            messagebox.showwarning("Attention", "Veuillez entrer un nom de base de données.")
            return False
        return True

    def add_job(self):
        if not self.validate_inputs(): return

        job = {
            "type": self.db_type_var.get(),
            "host": self.host_entry.get(),
            "port": self.port_entry.get(),
            "user": self.user_entry.get(),
            "pass": self.pass_entry.get(),
            "db": self.dbname_entry.get(),
            "dir": self.dir_var.get(),
            "freq": self.freq_var.get(),
            "time": self.time_entry.get()
        }
        self.jobs.append(job)
        self.update_listbox()
        self.save_config()
        self.apply_schedules()

    def remove_job(self):
        selection = self.job_listbox.curselection()
        if selection:
            index = selection[0]
            del self.jobs[index]
            self.update_listbox()
            self.save_config()
            self.apply_schedules()

    def update_listbox(self):
        self.job_listbox.delete(0, tk.END)
        for job in self.jobs:
            desc = f"[{job['type']}] {job['db']} -> {job['dir']} ({job['freq']} à {job['time']})"
            self.job_listbox.insert(tk.END, desc)

    def apply_schedules(self):
        schedule.clear()
        for job in self.jobs:
            def task(j=job):
                run_backup(j['type'], j['host'], j['port'], j['user'], j['pass'], j['db'], j['dir'])

            if job['freq'] == "Horaire":
                schedule.every().hour.do(task)
            elif job['freq'] == "Quotidien":
                schedule.every().day.at(job['time']).do(task)

    def toggle_scheduler(self):
        if self.is_running:
            self.is_running = False
            self.toggle_btn.config(text="Démarrer Planificateur")
        else:
            if not self.jobs:
                messagebox.showwarning("Attention", "Aucune tâche planifiée à démarrer.")
                return
            self.is_running = True
            self.toggle_btn.config(text="Arrêter Planificateur")
            self.daemon_thread = threading.Thread(target=self.run_daemon, daemon=True)
            self.daemon_thread.start()

    def run_daemon(self):
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.jobs, f)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.jobs = json.load(f)
                self.update_listbox()
                self.apply_schedules()

if __name__ == "__main__":
    root = tk.Tk()
    app = BackupApp(root)
    root.mainloop()
