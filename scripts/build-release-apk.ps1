param(
    [string] $AndroidSdkPath = $(if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { 'D:\AndroidSdk' }),
    [string] $PythonExecutable = $env:CARPALY_PYTHON
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$ledgerPath = Join-Path $projectRoot 'config\android-version-ledger.json'
$ledger = Get-Content -LiteralPath $ledgerPath -Raw | ConvertFrom-Json
$versionName = [string] $ledger.current.versionName
$versionCode = [int] $ledger.current.versionCode
if ($ledger.current.channel -notin @('test', 'release')) {
    throw 'Current ledger assignment is not a CarPaly user version.'
}

foreach ($name in @('ANDROID_KEYSTORE_PATH', 'ANDROID_KEYSTORE_PASSWORD', 'ANDROID_KEY_ALIAS', 'ANDROID_KEY_PASSWORD')) {
    if (-not [Environment]::GetEnvironmentVariable($name)) {
        throw "Authorized Release signing input $name is missing; no APK will be built and no Debug fallback is allowed."
    }
}
if (-not $env:DIPLAY_AUTH_ASSETS_DIR) {
    throw 'DIPLAY_AUTH_ASSETS_DIR is required; no source-only APK will be delivered.'
}
$authDirectory = Join-Path $env:DIPLAY_AUTH_ASSETS_DIR 'offline-mfi'
foreach ($name in @('identity.pk8', 'certificate.p7b')) {
    $path = Join-Path $authDirectory $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -le 0) {
        throw "Required authorized runtime authentication input is missing or empty: offline-mfi\$name"
    }
}

$env:ANDROID_HOME = $AndroidSdkPath
$pythonPath = $PythonExecutable
if (-not $pythonPath) {
    foreach ($commandName in @('python.exe', 'python3.exe', 'py.exe')) {
        $candidate = Get-Command $commandName -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandType -eq 'Application' } |
            Select-Object -First 1
        if (-not $candidate -or $candidate.Source -match '\\WindowsApps\\python(?:3)?\.exe$') { continue }
        & $candidate.Source --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $pythonPath = $candidate.Source
            break
        }
    }
}
if (-not $pythonPath -or -not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'A working Python 3 executable is required; set CARPALY_PYTHON or pass -PythonExecutable.'
}
& $pythonPath --version *> $null
if ($LASTEXITCODE -ne 0) { throw 'The configured Python executable could not run.' }
& $pythonPath (Join-Path $projectRoot 'scripts\android_versioning.py') check
if ($LASTEXITCODE -ne 0) { throw 'Version ledger validation failed; no APK was built.' }

$artifacts = Join-Path $projectRoot "artifacts\v$versionName"
$fileName = "CarPaly-XingyueL-v$versionName.apk"
$destination = Join-Path $artifacts $fileName
$report = Join-Path $artifacts "$fileName.verification.json"
$checksum = Join-Path $artifacts "$fileName.sha256"
foreach ($path in @($destination, $report, $checksum)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to replace an existing delivered file: $path" }
}

$gradle = Join-Path $projectRoot 'gradlew.bat'
& $gradle -p $projectRoot :mobile:assembleRelease --stacktrace --no-configuration-cache --no-daemon
if ($LASTEXITCODE -ne 0) { throw 'Release build or pinned signing verification failed; no APK was copied.' }

$builtApk = Join-Path $projectRoot 'mobile\build\outputs\apk\release\mobile-release.apk'
if (-not (Test-Path -LiteralPath $builtApk -PathType Leaf)) { throw 'The expected Release APK output is missing.' }
if (-not (Test-Path -LiteralPath $artifacts -PathType Container)) { New-Item -ItemType Directory -Path $artifacts | Out-Null }

$preflightReport = Join-Path $env:TEMP ("carpaly-release-$([guid]::NewGuid().ToString('N')).json")
try {
    & (Join-Path $PSScriptRoot 'verify-release-apk.ps1') `
        -ApkPath $builtApk `
        -AuthenticationAssetsRoot $env:DIPLAY_AUTH_ASSETS_DIR `
        -AndroidSdkPath $AndroidSdkPath `
        -ReportPath $preflightReport
    if ($LASTEXITCODE -ne 0) { throw 'Post-build Release APK verification failed; no user-deliverable APK was copied.' }

    Copy-Item -LiteralPath $builtApk -Destination $destination
    & (Join-Path $PSScriptRoot 'verify-release-apk.ps1') `
        -ApkPath $destination `
        -AuthenticationAssetsRoot $env:DIPLAY_AUTH_ASSETS_DIR `
        -AndroidSdkPath $AndroidSdkPath `
        -ReportPath $report `
        -RequireCanonicalFileName `
        -RecordDelivery
    if ($LASTEXITCODE -ne 0) { throw 'Final Release APK verification failed; do not install or distribute this file.' }

    $hash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath $checksum -Value "$hash  $fileName" -Encoding ASCII
    Write-Output "APK=$destination"
    Write-Output "VERSION=$versionName"
    Write-Output "VERSION_CODE=$versionCode"
    Write-Output "SHA256=$hash"
    Write-Output "SIGNER_SHA256=$($ledger.releaseCertificateSha256)"
    Write-Output 'UPGRADE_POLICY=FRESH_INSTALL_REQUIRED'
    Write-Output "REPORT=$report"
}
finally {
    if (Test-Path -LiteralPath $preflightReport) { Remove-Item -LiteralPath $preflightReport -Force }
}
