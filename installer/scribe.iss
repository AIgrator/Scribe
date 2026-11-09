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
; app.log) lives in %LOCALAPPDATA%\Scribe. The uninstaller removes settings,
; logs and records and keeps the downloaded voice models by default.
; Downloaded voice models can take 1-2 GB, so the uninstaller keeps them by
; default: the "keep models" checkbox is checked, and a normal uninstall removes
; settings, logs and records but preserves models. Untick it to remove
; everything.
;
; Portable use is unaffected: put an empty portable.flag next to Scribe.exe and
; the app keeps all data in the program folder instead of %LOCALAPPDATA%.
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
english.UninstallDataTitle=Uninstall {#AppName}
russian.UninstallDataTitle=Удаление {#AppName}
english.UninstallDataText=Scribe keeps settings, logs, records and downloaded voice models in %LOCALAPPDATA%\Scribe. Uninstall removes settings, logs and records. Downloaded voice models can take 1-2 GB, so they are kept by default for a future reinstall; untick the box below to remove them too.
russian.UninstallDataText=Scribe хранит настройки, журналы, записи и скачанные модели в %LOCALAPPDATA%\Scribe. При удалении настройки, журналы и записи удаляются. Скачанные голосовые модели занимают 1-2 ГБ, поэтому по умолчанию они сохраняются для повторной установки; снимите галочку ниже, чтобы удалить и их.
english.KeepModels=Keep downloaded voice models (settings and records will still be deleted)
russian.KeepModels=Сохранить скачанные голосовые модели (настройки и записи всё равно будут удалены)
english.UninstallDataOk=Uninstall
russian.UninstallDataOk=Удалить
english.UninstallDataCancel=Cancel
russian.UninstallDataCancel=Отмена
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
var
  KeepModels: Boolean;

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

{ The data folder is removed on uninstall. Models are the only part worth
  keeping (they are large and can be re-used after a reinstall), so the
  checkbox starts checked and a normal uninstall preserves them. Unticking it
  removes everything. }
function AskKeepModels(): Boolean;
var
  Form: TSetupForm;
  Info: TNewStaticText;
  Choice: TNewCheckBox;
  OkButton, CancelButton: TNewButton;
  ButtonWidth: Integer;
begin
  Result := False;
  Form := CreateCustomForm(480, 240, False, True);
  try
    Form.Caption := ExpandConstant('{cm:UninstallDataTitle}');

    Info := TNewStaticText.Create(Form);
    Info.Parent := Form;
    Info.Left := ScaleX(12);
    Info.Top := ScaleY(12);
    Info.Width := Form.ClientWidth - ScaleX(24);
    Info.Height := ScaleY(96);
    Info.AutoSize := False;
    Info.WordWrap := True;
    Info.Caption := ExpandConstant('{cm:UninstallDataText}');

    Choice := TNewCheckBox.Create(Form);
    Choice.Parent := Form;
    Choice.Left := ScaleX(12);
    Choice.Top := ScaleY(116);
    Choice.Width := Form.ClientWidth - ScaleX(24);
    Choice.Caption := ExpandConstant('{cm:KeepModels}');
    Choice.Checked := True;

    OkButton := TNewButton.Create(Form);
    OkButton.Parent := Form;
    OkButton.Caption := ExpandConstant('{cm:UninstallDataOk}');
    OkButton.ModalResult := mrOk;
    OkButton.Default := True;
    OkButton.Height := ScaleY(23);
    OkButton.Top := Form.ClientHeight - ScaleY(33);

    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.Caption := ExpandConstant('{cm:UninstallDataCancel}');
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;
    CancelButton.Height := ScaleY(23);
    CancelButton.Top := OkButton.Top;

    ButtonWidth := Form.CalculateButtonWidth([OkButton.Caption, CancelButton.Caption]);
    OkButton.Width := ButtonWidth;
    CancelButton.Width := ButtonWidth;
    OkButton.Left := Form.ClientWidth - ScaleX(12) - CancelButton.Width - ScaleX(8) - OkButton.Width;
    CancelButton.Left := Form.ClientWidth - ScaleX(12) - CancelButton.Width;

    if Form.ShowModal() = mrOk then
    begin
      Result := True;
      KeepModels := Choice.Checked;
    end;
  finally
    Form.Free();
  end;
end;

function InitializeUninstall(): Boolean;
begin
  { Models are preserved by default, including silent uninstall. The prompt
    below only runs when the data folder exists and the uninstall is visible. }
  KeepModels := True;
  { Silent uninstall (scripts, package managers) never prompts. Models stay
    because KeepModels defaults to True; settings, logs and records are removed. }
  if UninstallSilent() then
  begin
    Result := True;
    Exit;
  end;
  if not DirExists(DataDir()) then
  begin
    Result := True;
    Exit;
  end;
  Result := AskKeepModels();
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

procedure DeleteDataDir();
var
  FindRec: TFindRec;
  Path: string;
begin
  if not DirExists(DataDir()) then
    Exit;
  if not KeepModels then
  begin
    DelTree(DataDir(), True, True, True);
    Exit;
  end;
  { Keep models/ and remove everything else: settings, logs, records. }
  if FindFirst(DataDir() + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') and
           (CompareText(FindRec.Name, 'models') <> 0) then
        begin
          Path := DataDir() + '\' + FindRec.Name;
          if DirExists(Path) then
            DelTree(Path, True, True, True)
          else
            DeleteFile(Path);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
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
