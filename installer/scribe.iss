; Inno Setup script for Scribe (per-user install).
;
; Build:
;   python -m PyInstaller scribe.spec
;   & "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\scribe.iss
; Output: dist\ScribeSetup.exe
;
; Per-user: the setup never elevates. The program goes to
; %LOCALAPPDATA%\Programs\Scribe, the Start Menu shortcut and the uninstall
; entry are per user (HKCU). Mutable data (settings.json, models, records,
; app.log) lives in %LOCALAPPDATA%\Scribe. The uninstaller removes the program
; and that folder completely: settings, logs, records and downloaded models.
;
; Inno Setup is a build-time tool only; it is not a project dependency.

#define AppName "Scribe"
; The release number is not repeated here: it is read from the built EXE, whose
; version resource scribe.spec generates from file_version_info.txt.
; Build dist\Scribe.exe first (pyinstaller scribe.spec), then compile this script.
#define AppExePath AddBackslash(SourcePath) + "..\dist\Scribe.exe"
#define AppVersion GetStringFileInfo(AppExePath, "ProductVersion")
#define AppPublisher "AIgrator"
#define AppURL "https://github.com/AIgrator/Scribe"
#define AppExeName "Scribe.exe"

[Setup]
; A stable AppId ties upgrades and the uninstall entry to this application.
AppId={{B7E4C2A1-9D38-4F6B-8A52-3C1E5D7F9B24}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Scribe
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=ScribeSetup
SetupIconFile=..\resources\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Scribe lives in the tray and ignores a normal close, so upgrades must be
; allowed to terminate it before replacing the exe.
CloseApplications=force
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
english.LaunchAtStartup=Start Scribe when I sign in to Windows
russian.LaunchAtStartup=Запускать Scribe при входе в Windows
english.CloseRunningFailed=Could not close Scribe. Close it manually (tray icon - Exit) and run the uninstaller again.
russian.CloseRunningFailed=Не удалось закрыть Scribe. Закройте её вручную (значок в трее - Выход) и запустите удаление снова.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "{cm:LaunchAtStartup}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Scribe"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Scribe"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Scribe"; ValueData: """{app}\{#AppExeName}"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,Scribe}"; Flags: nowait postinstall skipifsilent

[Code]
function DataDir(): string;
begin
  Result := ExpandConstant('{localappdata}\Scribe');
end;

{ Inno's CloseApplications covers the install phase only. On uninstall a
  running Scribe.exe is locked, so Windows keeps the process alive while its
  files are scheduled for deletion on reboot: the app disappears from disk but
  keeps working until the next reboot. Detect the process after the standard
  uninstall confirmation and stop it before removing anything. }
function IsScribeRunning(): Boolean;
var
  ResultCode: Integer;
  Output: TExecOutput;
  I: Integer;
begin
  Result := False;
  try
    if ExecAndCaptureOutput(ExpandConstant('{cmd}'),
        '/c tasklist /FI "IMAGENAME eq Scribe.exe" /NH', '',
        SW_HIDE, ewWaitUntilTerminated, ResultCode, Output) then
    begin
      for I := 0 to GetArrayLength(Output.StdOut) - 1 do
      begin
        if Pos('scribe.exe', Lowercase(Output.StdOut[I])) > 0 then
        begin
          Result := True;
          Exit;
        end;
      end;
    end;
  except
    Log('Scribe process check failed: ' + GetExceptionMessage);
  end;
end;

function StopScribe(): Boolean;
var
  ResultCode: Integer;
  I: Integer;
begin
  { Scribe lives in the tray and ignores WM_CLOSE, so a forced stop is needed. }
  Exec(ExpandConstant('{cmd}'), '/c taskkill /F /T /IM Scribe.exe', '',
       SW_HIDE, ewWaitUntilTerminated, ResultCode);
  { taskkill returns before the process is fully gone; poll briefly. }
  for I := 1 to 10 do
  begin
    if not IsScribeRunning() then
    begin
      Result := True;
      Exit;
    end;
    Sleep(300);
  end;
  Result := not IsScribeRunning();
end;

function EnsureScribeClosed(): Boolean;
begin
  Result := True;
  if not IsScribeRunning() then
    Exit;
  { The standard uninstall confirmation already means "remove everything",
    so do not ask a second time: stop the process and let the uninstaller
    delete all files, including the locked exe. }
  if not StopScribe() then
  begin
    if not UninstallSilent() then
      MsgBox(ExpandConstant('{cm:CloseRunningFailed}'), mbError, MB_OK);
    Result := False;
  end;
end;

procedure RemoveAutostartEntry();
var
  Value: string;
begin
  { The startup task may not have been selected during setup, but the user can
    still enable autostart from Settings. Remove only our own exe path so a
    different Scribe installation is not affected. }
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run',
                         'Scribe', Value) then
  begin
    if Pos(Lowercase(ExpandConstant('{app}')), Lowercase(Value)) > 0 then
      RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Scribe');
  end;
end;

{ The data folder is removed completely on uninstall: settings, logs, records
  and downloaded models. The standard uninstall confirmation already covers
  this, so no extra prompt is shown. }
procedure DeleteDataDir();
begin
  if DirExists(DataDir()) then
    DelTree(DataDir(), True, True, True);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    { usUninstall runs after the standard "remove Scribe and all components?"
      confirmation, so the user has already agreed to a full removal. Stop the
      running app without a second prompt; otherwise its locked exe and data
      files would survive the uninstall. Abort instead of leaving a half-removed
      installation if the process cannot be stopped. }
    if not EnsureScribeClosed() then
    begin
      Abort;
      Exit;
    end;
    RemoveAutostartEntry();
    DeleteDataDir();
  end;
end;
