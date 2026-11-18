$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force output\installer_payload | Out-Null
Copy-Item 'dist\张平PDF压缩器.exe' output\installer_payload\App.exe -Force
Get-Content installer_native.vbs -Raw -Encoding utf8 | Set-Content output\installer_payload\setup.vbs -Encoding unicode
Get-Content uninstall_native.vbs -Raw -Encoding utf8 | Set-Content output\installer_payload\uninstall.vbs -Encoding unicode
Copy-Item THIRD_PARTY_NOTICES.md output\installer_payload\NOTICES.txt -Force
$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=$PSScriptRoot\dist\ZhangPingPDF-Setup.exe
FriendlyName=ZhangPingPDF Setup
AppLaunched=$env:SystemRoot\System32\wscript.exe setup.vbs
PostInstallCmd=$env:SystemRoot\System32\cmd.exe /d /c exit 0
AdminQuietInstCmd=$env:SystemRoot\System32\wscript.exe setup.vbs
UserQuietInstCmd=$env:SystemRoot\System32\wscript.exe setup.vbs
SourceFiles=SourceFiles
[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
FILE0="App.exe"
FILE1="setup.vbs"
FILE2="uninstall.vbs"
FILE3="NOTICES.txt"
[SourceFiles]
SourceFiles0=$PSScriptRoot\output\installer_payload\
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
%FILE3%=
"@
$sed | Set-Content output\installer.sed -Encoding ascii
$process = Start-Process -FilePath "$env:SystemRoot\System32\iexpress.exe" -ArgumentList '/N','/Q',"$PSScriptRoot\output\installer.sed" -WindowStyle Hidden -PassThru -Wait
"IExpress exit: $($process.ExitCode)" | Set-Content output\native_installer_build.log
if (!(Test-Path dist\ZhangPingPDF-Setup.exe)) { throw 'IExpress did not produce an installer' }
Move-Item -LiteralPath "$PSScriptRoot\dist\ZhangPingPDF-Setup.exe" -Destination "$PSScriptRoot\dist\张平PDF压缩器-安装程序.exe" -Force
if (Test-Path -LiteralPath "$PSScriptRoot\dist\~ZhangPingPDF-Setup.DDF") { Remove-Item -LiteralPath "$PSScriptRoot\dist\~ZhangPingPDF-Setup.DDF" }
