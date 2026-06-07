; Inno Setup Script for DBBackupManager
; Requires Inno Setup to compile: https://jrsoftware.org/isinfo.php

[Setup]
AppName=DBBackupManager
AppVersion=1.0.0
AppPublisher=DBBackupManager Team
DefaultDirName={autopf}\DBBackupManager
DefaultGroupName=DBBackupManager
UninstallDisplayIcon={app}\DBBackupManager.exe
Compression=lzma2
SolidCompression=yes
OutputDir=.\Output
OutputBaseFilename=DBBackupManager_Setup
SetupIconFile=compiler:SetupClassicIcon.ico
; Allow installation without admin rights if desired, but typically database tools might need it depending on where they write backups.
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The source path assumes you run this script from the root directory AFTER running build_windows.bat
Source: "DBBackupManager\dist\DBBackupManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Note: Don't use "Flags: ignoreversion" on any shared system files

[Dirs]
Name: "{app}\backups"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Icons]
Name: "{group}\DBBackupManager"; Filename: "{app}\DBBackupManager.exe"
Name: "{group}\{cm:UninstallProgram,DBBackupManager}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\DBBackupManager"; Filename: "{app}\DBBackupManager.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DBBackupManager.exe"; Description: "{cm:LaunchProgram,DBBackupManager}"; Flags: nowait postinstall skipifsilent
