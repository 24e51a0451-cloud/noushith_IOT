$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$toolsRoot = Join-Path $PSScriptRoot '..\.android-tools'
New-Item -ItemType Directory -Force -Path $toolsRoot | Out-Null
$toolsRoot = (Resolve-Path $toolsRoot).Path
if (-not (Test-Path "$toolsRoot\jdk")) {
    Invoke-WebRequest -UseBasicParsing 'https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse' -OutFile "$toolsRoot\jdk.zip"
    Expand-Archive -LiteralPath "$toolsRoot\jdk.zip" -DestinationPath "$toolsRoot\java-extracted" -Force
    $jdkSource = Get-ChildItem "$toolsRoot\java-extracted" -Directory | Select-Object -First 1
    Copy-Item -LiteralPath $jdkSource.FullName -Destination "$toolsRoot\jdk" -Recurse
}
if (-not (Test-Path "$toolsRoot\gradle-8.11.1")) {
    if (-not (Test-Path "$toolsRoot\gradle.zip")) { Invoke-WebRequest -UseBasicParsing 'https://services.gradle.org/distributions/gradle-8.11.1-bin.zip' -OutFile "$toolsRoot\gradle.zip" }
    Invoke-WebRequest -UseBasicParsing 'https://services.gradle.org/distributions/gradle-8.11.1-bin.zip.sha256' -OutFile "$toolsRoot\gradle.sha256"
    $expectedHash = (Get-Content -LiteralPath "$toolsRoot\gradle.sha256" -Raw).Trim()
    if ((Get-FileHash "$toolsRoot\gradle.zip" -Algorithm SHA256).Hash.ToLower() -ne $expectedHash) { throw 'Gradle checksum mismatch' }
    Expand-Archive -LiteralPath "$toolsRoot\gradle.zip" -DestinationPath $toolsRoot -Force
}
if (-not (Test-Path "$toolsRoot\sdk\cmdline-tools\latest\bin\sdkmanager.bat")) {
    Invoke-WebRequest -UseBasicParsing 'https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip' -OutFile "$toolsRoot\sdk.zip"
    Expand-Archive -LiteralPath "$toolsRoot\sdk.zip" -DestinationPath "$toolsRoot\sdk-extracted" -Force
    New-Item -ItemType Directory -Force -Path "$toolsRoot\sdk\cmdline-tools" | Out-Null
    Copy-Item -LiteralPath "$toolsRoot\sdk-extracted\cmdline-tools" -Destination "$toolsRoot\sdk\cmdline-tools\latest" -Recurse
}
Write-Output "Build tools downloaded to $toolsRoot"

