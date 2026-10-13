[CmdletBinding()]
param(
    [ValidateSet('dry-run', 'self-test', 'inspect-key', 'github-audit')]
    [string] $Mode = 'dry-run',
    [string] $PythonExe = 'python',
    [string] $PrivateKeyPath,
    [string] $KeyId
)

$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'ota_key_preflight.py'
if ($Mode -eq 'inspect-key' -and (-not $PrivateKeyPath -or -not $KeyId)) {
    throw 'inspect-key requires -PrivateKeyPath and -KeyId. Provide a file path only; never pass key contents.'
}

$pythonArgs = @($scriptPath, '--mode', $Mode)
if ($PrivateKeyPath) { $pythonArgs += @('--private-key', $PrivateKeyPath) }
if ($KeyId) { $pythonArgs += @('--key-id', $KeyId) }
& $PythonExe @pythonArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
