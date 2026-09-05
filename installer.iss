#define AppVersion "1.0.0"

[Setup]
AppId={{24B937C3-032A-4ECD-9824-A2643C79119E}
AppName=猫猫倒计时
AppVersion={#AppVersion}
AppPublisher=Li Aijie
AppPublisherURL=https://github.com/aijieli1/cat-countdown
AppSupportURL=https://github.com/aijieli1/cat-countdown/issues
AppUpdatesURL=https://github.com/aijieli1/cat-countdown/releases/latest
DefaultDirName={localappdata}\Programs\CatCountdown
DefaultGroupName=猫猫倒计时
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableFinishedPage=yes
UninstallDisplayIcon={app}\CountdownWidget.exe
SetupIconFile=cat.ico
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
OutputDir=installer-output
OutputBaseFilename=CatCountdown-Setup-Windows-x64

[Languages]
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Files]
Source: "dist\CountdownWidget\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\猫猫倒计时"; Filename: "{app}\CountdownWidget.exe"
Name: "{group}\猫猫倒计时"; Filename: "{app}\CountdownWidget.exe"
Name: "{group}\开启开机启动"; Filename: "{app}\CountdownWidget.exe"; Parameters: "--autostart-on"
Name: "{group}\关闭开机启动"; Filename: "{app}\CountdownWidget.exe"; Parameters: "--autostart-off"
Name: "{group}\卸载猫猫倒计时"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\CountdownWidget.exe"; Parameters: "--reveal"; Flags: nowait skipifsilent

[UninstallRun]
Filename: "{app}\CountdownWidget.exe"; Parameters: "--quit"; Flags: runhidden; RunOnceId: "StopWidget"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "CountdownWidget"; Flags: uninsdeletevalue

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\CountdownWidget.exe')) then
    Exec(ExpandConstant('{app}\CountdownWidget.exe'), '--quit', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;
