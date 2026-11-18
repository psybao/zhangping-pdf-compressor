$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force output,dist | Out-Null
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$(Split-Path (Get-Command python.exe).Source)"
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name '张平PDF压缩器' --icon assets\icon.ico --add-data 'product.json;.' --add-data 'assets;assets' --add-data 'licenses;licenses' --add-data 'THIRD_PARTY_NOTICES.md;.' --collect-data pdfdiet --collect-all pikepdf app.py *> output\pyinstaller.log
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed; see output/pyinstaller.log' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --name '张平PDF压缩器-便携版' --icon assets\icon.ico --workpath build\portable --add-data 'product.json;.' --add-data 'assets;assets' --add-data 'licenses;licenses' --add-data 'THIRD_PARTY_NOTICES.md;.' --collect-data pdfdiet --collect-all pikepdf app.py *> output\pyinstaller_portable.log
if ($LASTEXITCODE -ne 0) { throw 'Portable build failed' }
if (Test-Path 'tools\InnoSetup\ISCC.exe') { & 'tools\InnoSetup\ISCC.exe' installer.iss *> output\inno_build.log }
else { & .\build_native_installer.ps1 *> output\native_installer_build_console.log }
