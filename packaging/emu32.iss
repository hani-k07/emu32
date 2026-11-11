; Inno Setup script for the emu32 Windows installer.
; Build after PyInstaller, from the repository root:
;   ISCC /DAppVersion=1.2.3 packaging\emu32.iss
; Output: build\installer\emu32-setup.exe
;
; Installs for the current user by default, so no administrator rights are needed. When run
; as administrator, the user may choose to install for all users instead. Nothing is
; downloaded. Files go to the install folder, shortcuts to the Start Menu (and the desktop if
; chosen); the optional .asm association is stored in the user's (or machine's) registry.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define SourceDir "..\build\dist\emu32"

[Setup]
; The AppId identifies the program for upgrades and uninstall. Never change it.
AppId={{0D57C075-BD4A-4192-9B8C-48CF7BF43154}
AppName=emu32
AppVersion={#AppVersion}
AppVerName=emu32 {#AppVersion}
AppPublisher=hani-k07
AppPublisherURL=https://github.com/hani-k07/emu32
AppSupportURL=https://github.com/hani-k07/emu32/issues
AppComments=A tool for learning 32-bit x86 assembly
DefaultDirName={autopf}\emu32
DefaultGroupName=emu32
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
OutputDir=..\build\installer
OutputBaseFilename=emu32-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\emu32.exe
UninstallDisplayName=emu32 {#AppVersion}
ChangesAssociations=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associate"; Description: "Open .asm files with emu32"; GroupDescription: "File types:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\emu32"; Filename: "{app}\emu32.exe"
Name: "{autodesktop}\emu32"; Filename: "{app}\emu32.exe"; Tasks: desktopicon

[Registry]
; HKA is the current user's registry for a per-user install, the machine's for all users.
Root: HKA; Subkey: "Software\Classes\.asm\OpenWithProgids"; ValueType: string; ValueName: "emu32.asm"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\emu32.asm"; ValueType: string; ValueName: ""; ValueData: "Assembly source file"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\emu32.asm\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\emu32.exe,0"; Tasks: associate
Root: HKA; Subkey: "Software\Classes\emu32.asm\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\emu32.exe"" ""%1"""; Tasks: associate

[Run]
Filename: "{app}\emu32.exe"; Description: "{cm:LaunchProgram,emu32}"; Flags: nowait postinstall skipifsilent
