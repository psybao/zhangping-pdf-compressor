$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force output,dist,shared | Out-Null
if (Test-Path tools\jdk17) {
    $bundledJdk = Get-ChildItem tools\jdk17 -Directory | Select-Object -First 1
    if ($bundledJdk) { $env:JAVA_HOME = $bundledJdk.FullName }
}
if (!(Test-Path "$env:JAVA_HOME\bin\java.exe")) { throw 'Set JAVA_HOME to a JDK 17 installation before building Android.' }
if (!(Test-Path android\local.properties)) {
    $sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
    if (!(Test-Path $sdkRoot)) { throw 'Install Android SDK 35 and set ANDROID_HOME, or create android/local.properties with sdk.dir.' }
    ('sdk.dir=' + $sdkRoot.Replace('\','/')) | Set-Content android\local.properties -Encoding ascii
}
Copy-Item product.json shared\product.json -Force
Push-Location android
try {
    & .\gradlew.bat :app:assembleDebug :app:assembleRelease *> ..\output\android_build.log
    if ($LASTEXITCODE -ne 0) { throw 'Android build failed; see output/android_build.log' }
} finally { Pop-Location }
Copy-Item android\app\build\outputs\apk\debug\app-debug.apk 'dist\张平PDF压缩器-Android-debug.apk' -Force
