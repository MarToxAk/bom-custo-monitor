[Setup]
AppName=Bom Custo
AppVersion=1.0.2
DefaultDirName={autopf}\BomCusto
DefaultGroupName=Bom Custo
OutputDir=dist
OutputBaseFilename=BomCustoInstaller
SetupIconFile=status.ico

[Files]
Source: "dist\\BomCustoMonitor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "status.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Bom Custo"; Filename: "{app}\BomCustoMonitor.exe"; IconFilename: "{app}\status.ico"
Name: "{userdesktop}\Bom Custo"; Filename: "{app}\BomCustoMonitor.exe"; IconFilename: "{app}\status.ico"; Tasks: desktopicon
Name: "{userstartup}\Bom Custo"; Filename: "{app}\BomCustoMonitor.exe"; IconFilename: "{app}\status.ico"; Tasks: startup

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Opções adicionais:"
Name: "startup"; Description: "Iniciar automaticamente com o Windows"; GroupDescription: "Opções adicionais:"

[Run]
Filename: "{app}\BomCustoMonitor.exe"; Description: "Abrir Bom Custo após instalar"; Flags: nowait postinstall skipifsilent