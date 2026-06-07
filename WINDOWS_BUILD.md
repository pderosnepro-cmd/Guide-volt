# Créer un installateur Windows pour DBBackupManager

Pour obtenir un fichier `.exe` installable classique (type `setup.exe`) pour Windows, vous pouvez utiliser les scripts fournis.

## Prérequis

1.  **Python** doit être installé sur votre système Windows (et ajouté au PATH).
2.  **Inno Setup** doit être installé. C'est un outil gratuit et standard pour créer des installeurs Windows. Vous pouvez le télécharger ici : [https://jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php).

## Étape 1 : Compiler l'application (PyInstaller)

La première étape consiste à transformer les scripts Python en un exécutable autonome.

1.  Ouvrez un terminal (Invite de commandes ou PowerShell) dans le dossier racine du projet.
2.  Exécutez le script batch suivant :
    ```cmd
    build_windows.bat
    ```
3.  Ce script va installer `pyinstaller` (si nécessaire), installer les dépendances du projet depuis `requirements.txt`, et générer le dossier compilé dans `DBBackupManager\dist\DBBackupManager\`.

## Étape 2 : Générer le fichier d'installation (Inno Setup)

Une fois l'application compilée avec l'Étape 1, vous pouvez créer l'installateur :

1.  Assurez-vous d'avoir installé **Inno Setup**.
2.  Double-cliquez sur le fichier **`installer.iss`** à la racine du projet. Cela ouvrira l'éditeur d'Inno Setup.
3.  Dans l'éditeur, cliquez sur le bouton **Compile** (ou appuyez sur `Ctrl+F9`).
4.  Inno Setup va compiler tous les fichiers dans un seul fichier d'installation.
5.  Une fois terminé, vous trouverez votre fichier d'installation prêt à être distribué : **`Output\DBBackupManager_Setup.exe`**.

Vous pouvez maintenant exécuter ce fichier `setup.exe` sur n'importe quelle machine Windows pour installer DBBackupManager !
