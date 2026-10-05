param([string]$Project = 'D:\GALATICX\BCI_remotecontroll_jiosaavn')
$ErrorActionPreference = 'Stop'
$toolsRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\.android-tools')).Path
$env:JAVA_HOME = "$toolsRoot\jdk"
$env:ANDROID_HOME = "$toolsRoot\sdk"
$env:GRADLE_USER_HOME = "$toolsRoot\gradle-cache"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$sdkManager = "$toolsRoot\sdk\cmdline-tools\latest\bin\sdkmanager.bat"
1..100 | ForEach-Object { 'y' } | & $sdkManager --sdk_root=$env:ANDROID_HOME --licenses
if ($LASTEXITCODE -ne 0) { throw 'SDK license setup failed' }
& $sdkManager --sdk_root=$env:ANDROID_HOME 'platforms;android-35' 'build-tools;35.0.0' 'platform-tools'
if ($LASTEXITCODE -ne 0) { throw 'SDK installation failed' }
& "$toolsRoot\gradle-8.11.1\bin\gradle.bat" -p $Project wrapper --gradle-version 8.11.1 --no-daemon
if ($LASTEXITCODE -ne 0) { throw 'Gradle wrapper generation failed' }
& "$Project\gradlew.bat" -p $Project testDebugUnitTest lintDebug assembleDebug --no-daemon
if ($LASTEXITCODE -ne 0) { throw 'Android verification/build failed' }
Get-FileHash -LiteralPath "$Project\app\build\outputs\apk\debug\app-debug.apk" -Algorithm SHA256
