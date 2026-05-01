; BaixaTrack - Inno Setup script
; Compilar com: ISCC.exe installer.iss   (ou via build.bat)
; Pré-requisito: Inno Setup 6  (winget install JRSoftware.InnoSetup)

#define MyAppName        "BaixaTrack"
; Versao pode ser sobrescrita via linha de comando: ISCC.exe /DMyAppVersion=1.2.3 installer.iss
#ifndef MyAppVersion
  #define MyAppVersion   "1.0.0"
#endif
#define MyAppPublisher   "bdsromulo"
#define MyAppURL         "https://github.com/bdsromulo/BaixaTrack"
#define MyAppExeName     "BaixaTrack.exe"
#define MyAppSourceDir   "dist\BaixaTrack"

[Setup]
; AppId é o GUID que identifica este produto no Painel de Controle.
; Não troque depois de publicado — senão atualizações instalam por cima como apps separados.
AppId={{7B2D8E9C-4F3A-4F2B-8C1A-9D6E5A4B3C2D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableProgramGroupPage=yes
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest

OutputDir=dist
OutputBaseFilename=BaixaTrack-Setup
SetupIconFile=assets\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; Reservar ~170 MB para o FFmpeg baixado em %APPDATA% na primeira execucao do app.
; Sem isso o Inno Setup so contabiliza os ~52 MB dos arquivos do bundle.
ExtraDiskSpaceRequired=178257920

LicenseFile=LICENSE
; Mostra o tamanho final estimado na tela de confirmacao
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english";             MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copia toda a pasta do PyInstaller (--onedir) para o diretório de instalação.
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Atalho no Menu Iniciar (sempre criado)
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
; Atalho na Area de Trabalho (opcional - tarefa "desktopicon")
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Atalho para desinstalar
Name: "{autoprograms}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Checkbox "Executar BaixaTrack agora" no final do instalador (marcado por padrao)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
