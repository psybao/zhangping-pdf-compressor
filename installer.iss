#define AppName "张平PDF压缩器"
[Setup]
AppId={{5C43F12B-25E7-43BA-80D5-C593E9EFC61A}
AppName={#AppName}
AppVersion=1.0.0
AppPublisher=可达包
DefaultDirName={localappdata}\Programs\ZhangPingPDF
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=张平PDF压缩器-安装程序
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\张平PDF压缩器.exe
[Files]
Source: "dist\张平PDF压缩器.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.md"; DestDir: "{app}"
Source: "licenses\*"; DestDir: "{app}\licenses"; Flags: recursesubdirs createallsubdirs
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\张平PDF压缩器.exe"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\张平PDF压缩器.exe"
