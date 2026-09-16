; Inno Setup script for Sensei Index 4.0.
;
; Packages the PyInstaller onedir build (SenseiIndex.exe + its _internal\
; runtime folder - no loose, readable .py source anywhere in it) together
; with the app's real data files into one setup.exe. Run from Windows:
;     ISCC.exe installer.iss
; after "pyinstaller sensei_index.spec" has already produced
; packaging\dist\SenseiIndex\. The GitHub Actions workflow does both
; steps in order; see .github/workflows/build-windows-installer.yml.
;
; APP_VERSION (any free-form string, shown to the user in Add/Remove
; Programs) and APP_VERSION_INFO (strictly numeric, up to 4 dot-separated
; parts - Windows' own binary version metadata format, it'll fail to
; compile with anything else) can both be overridden from the command
; line, e.g.:
;     ISCC.exe /DAPP_VERSION=4.1.0 /DAPP_VERSION_INFO=4.1.0.0 installer.iss
; The CI workflow passes both, derived from the run number, on every
; build. Kept as two separate macros so a free-form APP_VERSION (or one
; left at its default) can never break the compile by landing in the
; numeric-only field.
#ifndef APP_VERSION
  #define APP_VERSION "4.0.0"
#endif
#ifndef APP_VERSION_INFO
  #define APP_VERSION_INFO "4.0.0.0"
#endif

#define AppName "Sensei Index"
#define AppExeName "SenseiIndex.exe"

[Setup]
; Fixed GUID so Windows recognizes upgrades as upgrades, not a second
; parallel install - never change this once it's shipped once.
AppId={{431240B9-68B8-4A35-9F0B-3B7B4AD8F438}
AppName={#AppName}
AppVersion={#APP_VERSION}
VersionInfoVersion={#APP_VERSION_INFO}
DefaultDirName={userpf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=..\assets\oathplatehelm.ico
OutputDir=installer_output
OutputBaseFilename=SenseiIndex-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; No admin rights, no UAC prompt - installs into the current user's own
; profile (userpf = %LOCALAPPDATA%\Programs). The app itself writes its
; workbook and settings back into its own install folder on every save
; (see paths.py / bootstrap.py's _check_writable), which is exactly the
; kind of write that a Program Files install would silently block for a
; non-admin user - so this is a correctness choice, not just convenience.
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; The frozen application itself - exe + its _internal runtime folder.
; Overwritten on every install/upgrade, same as any normal app binary.
Source: "dist\SenseiIndex\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Fonts/icon/images the running app loads from disk next to itself
; (paths.py's ASSETS_DIR) - binary assets, not source, and also
; overwritten on upgrade like the app binary above.
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; A short, accurate readme for the installed copy (the repo's own
; README.txt / READ_ME_FIRST.txt describe the source checkout and the
; old run-from-Python flow, not this installer).
Source: "INSTALLED_README.txt"; DestDir: "{app}"; DestName: "READ ME.txt"; Flags: ignoreversion

; ---------------------------------------------------------------------
; Real user data: the workbook, the reference master list, app state,
; and the PDF templates. "onlyifdoesntexist" means these seed the
; install the FIRST time only - running a newer setup.exe over an
; existing install never overwrites live data with whatever snapshot
; happened to ship in that build. "uninsneveruninstall" means
; uninstalling the app leaves every one of these in place; nothing here
; is exe/DLL, it's the user's actual inspection records, and no
; uninstaller should ever delete those silently.
; ---------------------------------------------------------------------
Source: "..\Equipment_Inspection_Tracker.xlsx"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\Instrumentation Master List.xlsx"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\series_registry.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\app_settings.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\equipment_status.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\wizard_draft.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\Transmitter_Inspection_Test_Record_TEMPLATE.pdf"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\Pneumatically_Actuated_Valve_Check_Record_TEMPLATE.pdf"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "..\Gauge_Inspection_Record_TEMPLATE.pdf"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent
