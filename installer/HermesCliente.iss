#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "HERMES Cliente"
#define AppExeName "HermesCliente.exe"

[Setup]
AppId={{AAACD2F0-02B0-41C6-A680-1B0CA4B388B8}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=HERMES
DefaultDirName={autopf}\HERMES Cliente
DefaultGroupName=HERMES Cliente
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\instalador
OutputBaseFilename=HERMES-Cliente-Setup-{#AppVersion}
UninstallDisplayName={#AppName}
Uninstallable=yes
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "startup"; Description: "Iniciar HERMES al iniciar sesión de Windows para todos los usuarios"; GroupDescription: "Inicio automático:"; Flags: checkedonce

[Files]
Source: "..\dist\HermesCliente\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\HermesRegistro.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\HERMES Cliente"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Registrar equipo en inventario"; Filename: "{app}\HermesRegistro.exe"; WorkingDir: "{app}"
Name: "{commonstartup}\HERMES Cliente"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: startup

[UninstallDelete]
Type: files; Name: "{commonstartup}\HERMES Cliente.lnk"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if not Exec(
      ExpandConstant('{app}\HermesRegistro.exe'),
      '',
      ExpandConstant('{app}'),
      SW_SHOW,
      ewWaitUntilTerminated,
      ResultCode
    ) then
      MsgBox(
        'HERMES se instaló, pero no se pudo abrir el registro del inventario. ' +
        'Puedes intentarlo de nuevo desde el acceso directo "Registrar equipo en inventario".',
        mbError,
        MB_OK
      )
    else if ResultCode <> 0 then
      MsgBox(
        'HERMES se instaló, pero el inventario compartido no se confirmó. ' +
        'No se marcó el equipo como registrado. Puedes intentarlo de nuevo desde ' +
        'el acceso directo "Registrar equipo en inventario".',
        mbError,
        MB_OK
      );
  end;
end;
