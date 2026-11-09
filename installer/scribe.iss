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
; app.log) lives in %LOCALAPPDATA%\Scribe and is removed by the uninstaller.
; Downloaded voice models can take 1-2 GB, so the uninstaller asks whether to
; keep them: the checkbox is off by default, i.e. a normal uninstall removes
; everything, like Logos.
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
english.UninstallDataText=Scribe keeps settings, logs, records and downloaded models in %LOCALAPPDATA%\Scribe. This folder is removed on uninstall. Downloaded voice models can take 1-2 GB, so you can keep them for a future reinstall.
russian.UninstallDataText=Scribe хранит настройки, журналы, записи и скачанные модели в %LOCALAPPDATA%\Scribe. При удалении эта папка будет удалена. Скачанные голосовые модели занимают 1-2 ГБ, поэтому их можно сохранить для повторной установки.
english.KeepModels=Keep downloaded voice models (settings and records will still be deleted)
russian.KeepModels=Сохранить скачанные голосовые модели (настройки и записи всё равно будут удалены)
english.UninstallDataOk=Uninstall
russian.UninstallDataOk=Удалить
english.UninstallDataCancel=Cancel
russian.UninstallDataCancel=Отмена

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

{ The data folder is removed on uninstall. Models are the only part worth
  keeping (they are large and can be re-used after a reinstall), so the
  checkbox starts empty and a normal uninstall deletes everything. }
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
    Choice.Checked := False;

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
  KeepModels := False;
  { Silent uninstall (scripts, package managers) never prompts and removes
    everything, which is the normal default. }
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
    DeleteDataDir();
end;
