param(
    [string] $AndroidSdkPath = $(if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { 'D:\AndroidSdk' })
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$ledgerPath = Join-Path $projectRoot 'config\android-version-ledger.json'
$ledger = Get-Content -LiteralPath $ledgerPath -Raw | ConvertFrom-Json
$versionName = [string] $ledger.current.versionName
if ($ledger.current.channel -ne 'test') { throw 'Current ledger assignment is not a test version.' }

foreach ($name in @('ANDROID_KEYSTORE_PATH', 'ANDROID_KEYSTORE_PASSWORD', 'ANDROID_KEY_ALIAS', 'ANDROID_KEY_PASSWORD')) {
    if (-not [Environment]::GetEnvironmentVariable($name)) {
        throw "Authorized Release signing input $name is missing; no Debug fallback will be used."
    }
}
if (-not $env:DIPLAY_AUTH_ASSETS_DIR) {
    throw 'DIPLAY_AUTH_ASSETS_DIR is required for the standalone authenticated test APK.'
}

$artifacts = Join-Path $projectRoot 'artifacts'
$fileName = "CarPaly-XingyueL-v$versionName-Upgrade-Test.apk"
$destination = Join-Path $artifacts $fileName
$report = Join-Path $artifacts "$fileName.verification.json"
$checksum = Join-Path $artifacts "$fileName.sha256"
foreach ($path in @($destination, $report, $checksum)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to replace an existing delivered file: $path" }
}

$gradle = Join-Path $projectRoot 'gradlew.bat'
& $gradle -p $projectRoot :mobile:assembleCarPalyUpgradeTest --stacktrace --no-configuration-cache
if ($LASTEXITCODE -ne 0) { throw 'Release-signed upgrade-test build failed; no user-deliverable APK was copied.' }

$builtApk = Join-Path $projectRoot 'mobile\build\outputs\apk\release\mobile-release.apk'
if (-not (Test-Path -LiteralPath $builtApk -PathType Leaf)) { throw 'The expected Release APK output is missing.' }
if (-not (Test-Path -LiteralPath $artifacts -PathType Container)) { New-Item -ItemType Directory -Path $artifacts | Out-Null }

$preflightReport = Join-Path $env:TEMP ("carpaly-upgrade-$([guid]::NewGuid().ToString('N')).json")
& (Join-Path $PSScriptRoot 'verify-upgrade-apk.ps1') `
    -ApkPath $builtApk `
    -AuthenticationAssetsRoot $env:DIPLAY_AUTH_ASSETS_DIR `
    -AndroidSdkPath $AndroidSdkPath `
    -ReportPath $preflightReport
if ($LASTEXITCODE -ne 0) { throw 'Post-build APK verification failed; no user-deliverable APK was copied.' }

Copy-Item -LiteralPath $builtApk -Destination $destination

& (Join-Path $PSScriptRoot 'verify-upgrade-apk.ps1') `
    -ApkPath $destination `
    -AuthenticationAssetsRoot $env:DIPLAY_AUTH_ASSETS_DIR `
    -AndroidSdkPath $AndroidSdkPath `
    -ReportPath $report `
    -RecordDelivery
if ($LASTEXITCODE -ne 0) { throw 'Post-build APK verification failed; do not install or distribute this file.' }

$hash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $checksum -Value "$hash  $fileName" -Encoding ASCII
Write-Output "APK=$destination"
Write-Output "SHA256=$hash"
Write-Output "REPORT=$report"
