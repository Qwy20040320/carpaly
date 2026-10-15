#requires -Version 5.1
[CmdletBinding()]
param(
    [switch] $CheckOnly,
    [switch] $SkipTests,
    [switch] $PrepareGitHub,
    [switch] $PrepareDraft,
    [switch] $Status,
    [string] $OutputDir,
    [switch] $VerboseLog,
    [switch] $FullPrepare,
    [string] $BuildMainCommit,
    [string] $AndroidSdkPath = $(if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { 'D:\AndroidSdk' }),
    [string] $PythonExecutable = $env:CARPALY_PYTHON
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = $PSScriptRoot
Import-Module (Join-Path $projectRoot 'scripts\ReleaseSystem.Core.psm1') -Force
$repo = 'Qwy20040320/carpaly'
$stateRoot = Join-Path $projectRoot '.private\local-release-state'
$ledgerPath = Join-Path $projectRoot 'config\android-version-ledger.json'
$ledger = Get-Content -LiteralPath $ledgerPath -Raw | ConvertFrom-Json
$versionName = [string] $ledger.current.versionName
$versionCode = [int] $ledger.current.versionCode
$tag = "v$versionName"
$apkName = "CarPaly-XingyueL-v$versionName.apk"
$artifactDir = if ($OutputDir) { [IO.Path]::GetFullPath($OutputDir) } else { Join-Path $projectRoot "artifacts\release\v$versionName" }
$isCandidate = [bool] $SkipTests
$localApkDir = if ($isCandidate) { Join-Path $projectRoot ".private\build-candidates\v$versionName" } else { $artifactDir }
$statePath = Join-Path $stateRoot "v$versionName.json"
$verbosePath = Join-Path $projectRoot ".private\release-logs\v$versionName-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')).log"
$exitBlocked = $false

function Write-Phase([string] $Text) { Write-Host "`n== $Text ==" -ForegroundColor Cyan }
function Write-Result([string] $Name, [string] $Status, [string] $Detail = '') {
    if ($Detail) { Write-Host "$Name=$Status $Detail" } else { Write-Host "$Name=$Status" }
}
function Save-State([string] $State, [string] $Evidence, [string] $Commit = '') {
    Set-CarPalyLocalReleaseState -Path $statePath -VersionName $versionName -State $State -Evidence $Evidence -Commit $Commit
}
function Get-PythonPath {
    if ($PythonExecutable) {
        if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) { throw 'Configured Python executable is missing.' }
        return $PythonExecutable
    }
    foreach ($name in @('python.exe', 'python3.exe', 'py.exe')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Where-Object { $_.CommandType -eq 'Application' } | Select-Object -First 1
        if ($command -and $command.Source -notmatch '\\WindowsApps\\python(?:3)?\.exe$') {
            & $command.Source --version *> $null
            if ($LASTEXITCODE -eq 0) { return $command.Source }
        }
    }
    throw 'Python 3 executable is unavailable; set CARPALY_PYTHON.'
}
function Invoke-Logged {
    param([Parameter(Mandatory = $true)][string] $Name, [Parameter(Mandatory = $true)][string] $Executable, [string[]] $Arguments = @())
    Write-Host "执行：$Name"
    $captured = @(& $Executable @Arguments 2>&1)
    $code = $LASTEXITCODE
    $text = ($captured | Out-String -Width 4096)
    $safe = Protect-CarPalyText $text
    if ($VerboseLog) {
        $logParent = Split-Path -Parent $verbosePath
        if (-not (Test-Path -LiteralPath $logParent -PathType Container)) { New-Item -ItemType Directory -Path $logParent -Force | Out-Null }
        Add-Content -LiteralPath $verbosePath -Value "[$([DateTime]::UtcNow.ToString('o'))] $Name (exit=$code)`n$safe" -Encoding UTF8
        if ($safe.Trim()) { Write-Verbose $safe.TrimEnd() }
    }
    if ($code -ne 0) { throw "$Name failed (exit=$code). Sensitive command output was not emitted." }
    return $text
}
function Get-GitValue([string[]] $Arguments) {
    $text = Invoke-Logged -Name "Git $($Arguments[0])" -Executable 'git' -Arguments $Arguments
    return $text.Trim()
}
function Resolve-AndroidEnvironment {
    $rows = [System.Collections.Generic.List[object]]::new()
    $java = Get-Command java -ErrorAction SilentlyContinue
    $javaVersion = ''
    if ($java) {
        $versionText = (& java -version 2>&1 | Out-String)
        $match = [regex]::Match($versionText, 'version "(?:1\.)?(\d+)')
        if ($match.Success) { $javaVersion = $match.Groups[1].Value }
    }
    $rows.Add([pscustomobject]@{ Check='JDK'; Status=if ($javaVersion -and [int]$javaVersion -ge 17) {'PASS'} else {'BLOCKED'}; Detail=if ($javaVersion) {"major=$javaVersion"} else {'java missing or version unreadable'} })
    $rows.Add([pscustomobject]@{ Check='ANDROID_SDK'; Status=if (Test-Path -LiteralPath (Join-Path $AndroidSdkPath 'platform-tools\adb.exe')) {'PASS'} else {'BLOCKED'}; Detail=if (Test-Path -LiteralPath (Join-Path $AndroidSdkPath 'platform-tools\adb.exe')) {'adb present'} else {'SDK platform-tools missing'} })
    $buildTools = Join-Path $AndroidSdkPath 'build-tools\36.0.0'
    $toolsReady = (Test-Path -LiteralPath (Join-Path $buildTools 'apksigner.bat')) -and (Test-Path -LiteralPath (Join-Path $buildTools 'aapt.exe'))
    $rows.Add([pscustomobject]@{ Check='ANDROID_BUILD_TOOLS'; Status=if ($toolsReady) {'PASS'} else {'BLOCKED'}; Detail=if ($toolsReady) {'36.0.0'} else {'apksigner/aapt missing'} })
    $rows.Add([pscustomobject]@{ Check='GRADLE_WRAPPER'; Status=if ((Test-Path (Join-Path $projectRoot 'gradlew.bat')) -and (Test-Path (Join-Path $projectRoot 'gradle\wrapper\gradle-wrapper.properties'))) {'PASS'} else {'BLOCKED'}; Detail='wrapper files' })
    $rows.Add([pscustomobject]@{ Check='GIT'; Status=if (Get-Command git -ErrorAction SilentlyContinue) {'PASS'} else {'BLOCKED'}; Detail='git executable' })
    $rows.Add([pscustomobject]@{ Check='GITHUB_CLI'; Status=if (Get-Command gh -ErrorAction SilentlyContinue) {'PASS'} else {'BLOCKED'}; Detail='gh executable' })
    try { $null = Get-PythonPath; $rows.Add([pscustomobject]@{ Check='PYTHON'; Status='PASS'; Detail='Python 3 executable' }) }
    catch { $rows.Add([pscustomobject]@{ Check='PYTHON'; Status='BLOCKED'; Detail='Python 3 executable unavailable' }) }
    $secretNames = @('ANDROID_KEYSTORE_PATH', 'ANDROID_KEYSTORE_PASSWORD', 'ANDROID_KEY_ALIAS', 'ANDROID_KEY_PASSWORD')
    $missing = @($secretNames | Where-Object { -not [Environment]::GetEnvironmentVariable($_) })
    $rows.Add([pscustomobject]@{ Check='RELEASE_SIGNING_INPUTS'; Status=if ($missing.Count -eq 0) {'PRESENT_NOT_YET_VERIFIED'} else {'BLOCKED'}; Detail=if ($missing.Count -eq 0) {'all required names present; values withheld'} else {"missing=$($missing -join ',')"} })
    $authRoot = $env:DIPLAY_AUTH_ASSETS_DIR
    $authReady = $false
    if ($authRoot) {
        $authReady = (Test-Path -LiteralPath (Join-Path $authRoot 'offline-mfi\identity.pk8') -PathType Leaf) -and (Test-Path -LiteralPath (Join-Path $authRoot 'offline-mfi\certificate.p7b') -PathType Leaf)
    }
    $rows.Add([pscustomobject]@{ Check='RUNTIME_AUTH_ASSETS'; Status=if ($authReady) {'PRESENT_NOT_CONTENT_AUDITED'} else {'BLOCKED'}; Detail=if ($authReady) {'required local filenames present; contents not displayed'} else {'required local asset pair unavailable'} })
    return ,$rows
}
function Get-WorkingPaths {
    $changed = @()
    $changed += @(git diff --name-only)
    $changed += @(git diff --cached --name-only)
    $changed += @(git ls-files --others --exclude-standard)
    return @($changed | Where-Object { $_ } | Sort-Object -Unique)
}
function Assert-PublicSafePaths([string[]] $Paths) {
    $unsafe = @($Paths | Where-Object {
        $_ -match '(^|/)(\.private|offline-mfi|artifacts|build|\.gradle)(/|$)' -or
        $_ -match '(?i)\.(apk|aab|jks|keystore|p12|pfx|pk8|p7b|pem|key|log|zip|7z|rar|db|sqlite|dmp|bin|exe|dll)$' -or
        $_ -match '(?i)(^|/)(local\.properties|release-signing\.properties)$' -or
        $_ -match '^scripts/collect-geely-.*diagnostics\.ps1$'
    })
    if ($unsafe.Count) { throw "Sensitive/private paths block automatic staging: $($unsafe -join ', ')" }
}
function Test-HighRiskChanges([string[]] $Paths) {
    $patterns = @(
        '^\.github/workflows/', '^\.github/scripts/', '^config/android-version-ledger\.json$',
        '^config/release-intent\.json$', '^config/release-review-policy\.json$',
        '^config/release-source-policy\.json$', '^mobile/build\.gradle\.kts$',
        '^scripts/(android_versioning\.py|build-release-apk\.ps1|verify-release-apk\.ps1|release_automation\.py|release_review_gate\.py|check_release_signer_pin\.py)$',
        '(^|/)offline-mfi/'
    )
    foreach ($path in $Paths) { foreach ($pattern in $patterns) { if ($path -match $pattern) { return $true } } }
    return $false
}
function Get-ProtectionEvidence {
    $policy = Get-Content -LiteralPath (Join-Path $projectRoot 'config\release-review-policy.json') -Raw | ConvertFrom-Json
    $listed = Get-GhJson @('api',"repos/$repo/rulesets")
    $matches = @($listed | Where-Object { $_.name -eq $policy.mainRulesetName -and $_.enforcement -eq 'active' })
    if ($matches.Count -ne 1) { throw 'Active main ruleset could not be uniquely verified; Auto-merge will not be requested.' }
    $detail = Get-GhJson @('api',"repos/$repo/rulesets/$($matches[0].id)")
    $include = @($detail.conditions.ref_name.include)
    if ($include -notcontains '~DEFAULT_BRANCH' -and $include -notcontains 'refs/heads/main') { throw 'The active ruleset does not explicitly protect main.' }
    $types = @($detail.rules | ForEach-Object { $_.type })
    $statusRule = @($detail.rules | Where-Object { $_.type -eq 'required_status_checks' }) | Select-Object -First 1
    $prRule = @($detail.rules | Where-Object { $_.type -eq 'pull_request' }) | Select-Object -First 1
    if (-not $statusRule -or -not $prRule) { throw 'Ruleset lacks required status checks or PR rules.' }
    $contexts = @($statusRule.parameters.required_status_checks | ForEach-Object { $_.context })
    if ($contexts.Count -eq 0) { throw 'No required status checks are configured for main.' }
    $requiredReviews = [int] $prRule.parameters.required_approving_review_count
    if ($policy.mode -eq 'multi_maintainer' -and $requiredReviews -lt [int]$policy.minimumIndependentApprovals) {
        throw 'GitHub ruleset approval requirement is weaker than the reviewed multi-maintainer policy.'
    }
    if ($types -notcontains 'non_fast_forward' -or $types -notcontains 'deletion' -or @($detail.bypass_actors).Count -gt 0) {
        throw 'Main ruleset lacks non-fast-forward/deletion protection or has bypass actors.'
    }
    return [pscustomobject]@{
        Name = [string]$policy.mainRulesetName
        RequiredChecks = $contexts
        RequiredReviews = $requiredReviews
        ReviewPolicy = $policy
        Detail = $detail
    }
}
function Test-AutoMergeEligibility {
    param([int] $PullNumber, [string] $ExpectedHead, [string[]] $ChangedPaths)
    $repositoryInfo = Get-GhJson @('api',"repos/$repo")
    $protection = Get-ProtectionEvidence
    $pr = Get-GhJson @('pr','view',[string]$PullNumber,'--repo',$repo,'--json','state,isDraft,baseRefName,headRefOid,headRepository,mergeable,author,authorAssociation,reviews')
    $prChecks = Get-GhJson @('pr','checks',[string]$PullNumber,'--repo',$repo,'--json','name,state')
    $unresolvedThreads = $false
    $cursor = $null
    $threadQuery = 'query($owner:String!,$name:String!,$number:Int!,$cursor:String){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100,after:$cursor){nodes{isResolved} pageInfo{hasNextPage endCursor}}}}}'
    do {
        $graphqlArgs = @('api','graphql','-F','owner=Qwy20040320','-F','name=carpaly','-F',"number=$PullNumber",'-f',"query=$threadQuery")
        if ($cursor) { $graphqlArgs += @('-F',"cursor=$cursor") }
        $threadData = Get-GhJson $graphqlArgs
        $threads = @($threadData.data.repository.pullRequest.reviewThreads.nodes)
        if ($threads | Where-Object { $_.isResolved -ne $true }) { $unresolvedThreads = $true }
        $hasNext = [bool]$threadData.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage
        $cursor = [string]$threadData.data.repository.pullRequest.reviewThreads.pageInfo.endCursor
    } while ($hasNext)
    $reviewQuery = 'query($owner:String!,$name:String!,$number:Int!,$cursor:String){repository(owner:$owner,name:$name){pullRequest(number:$number){reviews(first:100,after:$cursor){nodes{author{login} state commit{oid}} pageInfo{hasNextPage endCursor}}}}}'
    $independentApprovals = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $reviewCursor = $null
    do {
        $reviewArgs = @('api','graphql','-F','owner=Qwy20040320','-F','name=carpaly','-F',"number=$PullNumber",'-f',"query=$reviewQuery")
        if ($reviewCursor) { $reviewArgs += @('-F',"cursor=$reviewCursor") }
        $reviewData = Get-GhJson $reviewArgs
        $reviewsPage = $reviewData.data.repository.pullRequest.reviews
        foreach ($review in @($reviewsPage.nodes)) {
            $reviewer = if ($review.author) { [string]$review.author.login } else { '' }
            $reviewCommit = if ($review.commit) { [string]$review.commit.oid } else { '' }
            if ($review.state -eq 'APPROVED' -and $reviewCommit -eq $ExpectedHead -and
                $reviewer -and -not [string]::Equals($reviewer, [string]$pr.author.login, [StringComparison]::OrdinalIgnoreCase)) {
                [void]$independentApprovals.Add($reviewer)
            }
        }
        $reviewHasNext = [bool]$reviewsPage.pageInfo.hasNextPage
        $reviewCursor = [string]$reviewsPage.pageInfo.endCursor
    } while ($reviewHasNext)
    $contexts = @{}
    foreach ($check in $prChecks) {
        $state = [string]$check.state
        $row = if ($state -eq 'SUCCESS') { @{ status='completed'; conclusion='success' } }
            elseif ($state -in @('FAILURE','CANCELLED','TIMED_OUT','ACTION_REQUIRED')) { @{ status='completed'; conclusion='failure' } }
            else { @{ status='in_progress'; conclusion='' } }
        $contexts[[string]$check.name] = $row
    }
    $headRepo = ''
    if ($pr.headRepository -and $pr.headRepository.nameWithOwner) { $headRepo = [string]$pr.headRepository.nameWithOwner }
    $mergeable = ($pr.mergeable -eq 'MERGEABLE' -or $pr.mergeable -eq $true)
    $evidence = [ordered]@{
        repository = @{ full_name=[string]$repositoryInfo.full_name; allow_auto_merge=[bool]$repositoryInfo.allow_auto_merge }
        pull_request = @{
            state=[string]$pr.state; draft=[bool]$pr.isDraft; base_ref=[string]$pr.baseRefName
            head_repo=$headRepo; mergeable=$mergeable; head_sha=[string]$pr.headRefOid
            author_login=[string]$pr.author.login; author_association=[string]$pr.authorAssociation
            independent_approvals=@($independentApprovals | Sort-Object)
            unresolved_review_threads=$unresolvedThreads
        }
        protection = @{
            active=($protection.Detail.enforcement -eq 'active'); target='main'
            allows_force_pushes=($protection.Detail.rules.type -notcontains 'non_fast_forward')
            allows_deletions=($protection.Detail.rules.type -notcontains 'deletion')
            bypass_actors=@($protection.Detail.bypass_actors)
            required_checks=@($protection.RequiredChecks)
            required_approving_review_count=$protection.RequiredReviews
        }
        checks = @{ head_sha=[string]$pr.headRefOid; contexts=$contexts }
        review_policy = $protection.ReviewPolicy
        changed_paths = $ChangedPaths
        expected_head_sha = $ExpectedHead
        requester_login = [string]$script:githubLogin
    }
    $inputPath = Join-Path $env:TEMP ("carpaly-automerge-evidence-" + [guid]::NewGuid().ToString('N') + '.json')
    try {
        Set-Content -LiteralPath $inputPath -Value ($evidence | ConvertTo-Json -Depth 12) -Encoding UTF8
        $python = Get-PythonPath
        $decision = & $python (Join-Path $projectRoot 'scripts/release_automation.py') auto-merge-check --input $inputPath 2>&1
        $decisionCode = $LASTEXITCODE
        return [pscustomobject]@{ Allowed=($decisionCode -eq 0); Text=(($decision | Out-String).Trim()); Head=[string]$pr.headRefOid }
    }
    finally { if (Test-Path -LiteralPath $inputPath) { Remove-Item -LiteralPath $inputPath -Force } }
}
function Wait-ForMergedPR {
    param([int] $PullNumber, [string] $ExpectedHead)
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $pr = Get-GhJson @('pr','view',[string]$PullNumber,'--repo',$repo,'--json','state,mergedAt,mergeCommit,headRefOid')
        if ($pr.headRefOid -ne $ExpectedHead) { throw 'PR head changed during native Auto-merge wait.' }
        if ($pr.state -eq 'MERGED' -and $pr.mergeCommit.oid) { return [string]$pr.mergeCommit.oid }
        if ($pr.state -eq 'CLOSED') { throw 'PR closed without a verified merge commit.' }
        Start-Sleep -Seconds 10
    }
    throw 'Native Auto-merge did not complete within the bounded wait; PR remains under GitHub rules.'
}
function Invoke-LocalChecks([switch] $IncludeGradle) {
    $python = Get-PythonPath
    Invoke-Logged -Name '公开源码树检查' -Executable $python -Arguments @((Join-Path $projectRoot 'scripts/check_public_tree.py')) | Out-Null
    Invoke-Logged -Name '版本元数据一致性检查' -Executable $python -Arguments @((Join-Path $projectRoot 'scripts/android_versioning.py'), 'check-ci') | Out-Null
    Invoke-Logged -Name '发布自动化安全静态检查' -Executable $python -Arguments @((Join-Path $projectRoot 'scripts/check_release_automation.py')) | Out-Null
    Invoke-Logged -Name '项目文档检查' -Executable $python -Arguments @((Join-Path $projectRoot 'scripts/check_project_docs.py')) | Out-Null
    Invoke-Logged -Name '发布器集成测试' -Executable $python -Arguments @((Join-Path $projectRoot 'scripts/test_release_pipeline.py')) | Out-Null
    Invoke-Logged -Name '发布策略与 OTA 测试' -Executable $python -Arguments @('-m','unittest','scripts.test_android_versioning','scripts.test_release_automation','scripts.test_release_intent','scripts.test_release_review_gate','scripts.test_release_signer_pin','scripts.test_release_pipeline','scripts.test_ota_manifest','scripts.test_build_site','scripts.test_preserve_ota_feeds') | Out-Null
    Invoke-Logged -Name '发布系统 PowerShell 单测' -Executable 'pwsh' -Arguments @('-NoLogo','-NoProfile','-File',(Join-Path $projectRoot 'scripts/test_build_release.ps1')) | Out-Null
    $gitleaks = Get-Command gitleaks -ErrorAction SilentlyContinue
    if (-not $gitleaks) { throw 'Gitleaks is unavailable; automatic GitHub sync is blocked.' }
    Invoke-Logged -Name 'Gitleaks 本地源码扫描（redacted）' -Executable $gitleaks.Source -Arguments @('dir', $projectRoot, '--redact', '--no-banner') | Out-Null
    if ($IncludeGradle) {
        $gradle = Join-Path $projectRoot 'gradlew.bat'
        Invoke-Logged -Name 'Gradle 单测、Lint 与内部 Debug CI' -Executable $gradle -Arguments @('-p',$projectRoot,':shared:testDebugUnitTest',':common:testDebugUnitTest',':home:testDebugUnitTest',':mobile:lintDebug',':home:lintDebug',':maphost:lintDebug',':mobile:assembleDebug',':home:assembleDebug',':maphost:assembleDebug','--stacktrace','--no-configuration-cache','--no-daemon') | Out-Null
    }
}
function Get-GhJson([string[]] $Arguments) {
    $raw = Invoke-Logged -Name "GitHub $($Arguments[0])" -Executable 'gh' -Arguments $Arguments
    try { return $raw | ConvertFrom-Json } catch { throw 'GitHub CLI returned invalid JSON.' }
}
function Invoke-ReadOnlyStatus {
    Write-Phase '当前本地与 GitHub 状态（只读）'
    Write-Result 'VERSION' 'INFO' "$versionName code=$versionCode package=$($ledger.applicationId)"
    $head = Get-GitValue @('rev-parse','HEAD')
    $branch = Get-GitValue @('branch','--show-current')
    Write-Result 'GIT_HEAD' 'INFO' $head
    Write-Result 'GIT_BRANCH' 'INFO' $branch
    $status = @(git status --short)
    Write-Result 'GIT_WORKTREE' $(if ($status.Count -eq 0) {'CLEAN'} else {'DIRTY'}) "entries=$($status.Count)"
    $apkPath = Join-Path $artifactDir $apkName
    Write-Result 'LOCAL_APK' $(if (Test-Path -LiteralPath $apkPath) {'PRESENT'} else {'NOT_BUILT'}) $apkPath
    if (Get-Command gh -ErrorAction SilentlyContinue) {
        $auth = & gh auth status 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Result 'GITHUB_LOGIN' 'PASS'
            $repoInfo = Get-GhJson @('api',"repos/$repo")
            Write-Result 'AUTO_MERGE_SETTING' $(if ($repoInfo.allow_auto_merge) {'ENABLED'} else {'DISABLED'})
            $pulls = Get-GhJson @('pr','list','--repo',$repo,'--base','main','--state','open','--json','number,url,isDraft,headRefName,headRefOid')
            foreach ($pull in $pulls) { Write-Result "PR_$($pull.number)" 'OPEN' "draft=$($pull.isDraft) head=$($pull.headRefOid) $($pull.url)" }
            $release = & gh release view $tag --repo $repo --json tagName,isDraft,isPrerelease,url,body 2>$null
            if ($LASTEXITCODE -eq 0) {
                $parsed = $release | ConvertFrom-Json
                Write-Result 'GITHUB_RELEASE' $(if ($parsed.isDraft) {'DRAFT'} else {'PUBLISHED'}) "$($parsed.tagName) $($parsed.url)"
                Write-Result 'GITHUB_RELEASE_CHANNEL' $(if ($parsed.isPrerelease) {'PRE_RELEASE'} else {'FORMAL'})
                $notesClaimPreRelease = [regex]::IsMatch([string]$parsed.body, '(?i)(?:发布类型\s*[：:]?\s*[^\n]{0,30}预发布|预发布测试版|\bpre-release\b|\bprerelease\b|\bbeta\b)')
                $channelConflict = (-not $parsed.isDraft) -and (-not $parsed.isPrerelease) -and $notesClaimPreRelease
                Write-Result 'GITHUB_RELEASE_METADATA_CONSISTENCY' $(if ($channelConflict) {'CONFLICT'} else {'CONSISTENT_OR_UNDETECTED'}) 'release body was inspected without modification'
            } else { Write-Result 'GITHUB_RELEASE' 'NOT_FOUND_OR_UNREADABLE' }
        } else { Write-Result 'GITHUB_LOGIN' 'BLOCKED' 'gh auth status failed' }
    } else { Write-Result 'GITHUB_LOGIN' 'BLOCKED' 'gh CLI missing' }
    if (Test-Path -LiteralPath $statePath) { Write-Host 'LOCAL_RELEASE_STATE='; Get-Content -LiteralPath $statePath }
    else { Write-Result 'LOCAL_RELEASE_STATE' 'NOT_STARTED' }
    $intentPath = Join-Path $projectRoot 'config\release-intent.json'
    $intent = Get-Content -LiteralPath $intentPath -Raw | ConvertFrom-Json
    Write-Result 'RELEASE_INTENT' $(if ($intent.enabled -eq $true) {'ENABLED'} else {'DISABLED'}) "candidate-channel=$($ledger.current.channel); no local mode activates publishing"
    Write-Result 'APK_UPLOAD' 'NEVER_AUTOMATIC' 'local release tool does not upload APKs'
    Write-Result 'VEHICLE_TEST' 'NOT_TESTED'
}
function Invoke-CheckOnly {
    Write-Phase '环境与发布门禁预检（不构建 APK）'
    $checks = Resolve-AndroidEnvironment
    foreach ($row in $checks) { Write-Result $row.Check $row.Status $row.Detail; if ($row.Status -eq 'BLOCKED') { $script:exitBlocked = $true } }
    $python = Get-PythonPath
    & $python (Join-Path $projectRoot 'scripts/android_versioning.py') check
    if ($LASTEXITCODE -ne 0) { Write-Result 'VERSION_HIGH_WATER' 'BLOCKED' 'current Gradle version is not eligible for a new Release'; $script:exitBlocked = $true }
    $sourceOutput = & $python (Join-Path $projectRoot 'scripts/release_automation.py') source-check --root $projectRoot 2>&1
    $sourceCode = $LASTEXITCODE
    Write-Result 'RELEASE_SOURCE_BASELINE' $(if ($sourceCode -eq 0) {'PASS'} else {'BLOCKED'}) (($sourceOutput | Out-String).Trim())
    if ($sourceCode -ne 0) { $script:exitBlocked = $true }
    $branch = (git branch --show-current).Trim()
    $head = (git rev-parse HEAD).Trim()
    $remoteMain = (git rev-parse origin/main 2>$null).Trim()
    $dirty = @(git status --porcelain)
    $cleanMain = if ($BuildMainCommit) {
        $branch -in @('', 'main') -and $head -eq $BuildMainCommit -and $remoteMain -eq $BuildMainCommit -and $dirty.Count -eq 0
    } else {
        $branch -eq 'main' -and $head -eq $remoteMain -and $dirty.Count -eq 0
    }
    Write-Result 'CLEAN_MAIN_SOURCE' $(if ($cleanMain) {'PASS'} else {'BLOCKED'}) "branch=$(if ($branch) {$branch} else {'DETACHED'}) dirtyEntries=$($dirty.Count)"
    if (-not $cleanMain) { $script:exitBlocked = $true }
    if ($checks | Where-Object { $_.Check -eq 'RELEASE_SIGNING_INPUTS' -and $_.Status -eq 'BLOCKED' }) { $script:exitBlocked = $true }
    if ($checks | Where-Object { $_.Check -eq 'RUNTIME_AUTH_ASSETS' -and $_.Status -eq 'BLOCKED' }) { $script:exitBlocked = $true }
    if ($script:exitBlocked) { Write-Result 'CHECK_ONLY' 'BLOCKED' 'no build started; resolve listed blockers first'; return 1 }
    $gradle = Join-Path $projectRoot 'gradlew.bat'
    try {
        Invoke-Logged -Name '签名预检任务' -Executable $gradle -Arguments @('-p',$projectRoot,':mobile:verifyCarPalyReleaseSigning','--no-daemon') | Out-Null
        Write-Result 'SIGNER_CERTIFICATE' 'PASS' 'Gradle validated signing identity; credential values withheld'
    } catch { Write-Result 'SIGNER_CERTIFICATE' 'BLOCKED' 'keystore, alias or password did not pass the non-outputting Gradle preflight'; return 1 }
    Write-Result 'CHECK_ONLY' 'PASS' 'no APK generated'
    return 0
}
function Invoke-Build {
    Write-Phase 'Release 构建预检'
    $code = Invoke-CheckOnly
    if ($code -ne 0) { throw 'Preflight blocked the Release build.' }
    if (-not $SkipTests) {
        Invoke-LocalChecks -IncludeGradle
    } else {
        Write-Result 'AUTOMATED_TESTS' 'SKIPPED' 'development-only candidate; RELEASE_READY=NO'
    }
    $python = Get-PythonPath
    Invoke-Logged -Name '严格版本高水位检查' -Executable $python -Arguments @((Join-Path $projectRoot 'scripts/android_versioning.py'),'check') | Out-Null
    $branch = (git branch --show-current).Trim()
    $head = (git rev-parse HEAD).Trim()
    $remoteMain = (git rev-parse origin/main).Trim()
    if ($BuildMainCommit) {
        if ($head -ne $BuildMainCommit -or $remoteMain -ne $BuildMainCommit -or $branch -notin @('', 'main')) {
            throw 'Isolated build commit is not the exact current origin/main commit.'
        }
    } elseif ($branch -ne 'main' -or $head -ne $remoteMain) { throw 'Signed user build must be built from clean current origin/main.' }
    if (@(git status --porcelain).Count -gt 0) { throw 'Signed user build requires a clean source worktree.' }
    if ($SkipTests -and -not $OutputDir) { $script:localApkDir = Join-Path $projectRoot ".private\build-candidates\v$versionName" }
    $expectedCommit = (git rev-parse HEAD).Trim()
    if (-not (Test-Path -LiteralPath $localApkDir -PathType Container)) { New-Item -ItemType Directory -Path $localApkDir -Force | Out-Null }
    $apkPath = Join-Path $localApkDir $apkName
    if (Test-Path -LiteralPath $apkPath -PathType Leaf) {
        $checksumPath = Join-Path $localApkDir 'SHA256SUMS.txt'
        if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) { throw 'An APK exists without its immutable checksum record; refusing to overwrite or reuse.' }
        $expectedHash = (Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ((Get-Content -LiteralPath $checksumPath -Raw) -notmatch [regex]::Escape($expectedHash)) { throw 'Existing APK checksum record does not match; no overwrite allowed.' }
        Write-Result 'EXISTING_APK' 'REUSE_CANDIDATE' $expectedHash
    } else {
        $builder = Join-Path $projectRoot 'scripts\build-release-apk.ps1'
        if ($SkipTests) {
            & $builder -AndroidSdkPath $AndroidSdkPath -PythonExecutable $python -OutputDir $localApkDir -CandidateOnly
        } else {
            & $builder -AndroidSdkPath $AndroidSdkPath -PythonExecutable $python -OutputDir $localApkDir
        }
        if ($LASTEXITCODE -ne 0) { throw 'Signed Release build/verification failed; no release-ready artifact.' }
    }
    $shaPath = Join-Path $localApkDir 'SHA256SUMS.txt'
    if (-not (Test-Path -LiteralPath $shaPath)) {
        $hash = (Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant()
        Set-Content -LiteralPath $shaPath -Value "$hash  $apkName" -Encoding ASCII
    }
    $verifyPath = "$apkPath.verification.json"
    $verifyReport = if (Test-Path -LiteralPath $verifyPath) { Get-Content -LiteralPath $verifyPath -Raw | ConvertFrom-Json } else { $null }
    if (-not $verifyReport -or $verifyReport.status -ne 'PASS' -or $verifyReport.versionCode -ne $versionCode -or $verifyReport.signerCertificateSha256 -ne (Get-CarPalySignerForVersion $ledger $versionCode)) {
        throw 'Final APK verification report is missing or conflicts with the version ledger.'
    }
    $tree = (git rev-parse HEAD^{tree}).Trim()
    $gradleVersion = (Invoke-Logged -Name 'Gradle 版本记录' -Executable (Join-Path $projectRoot 'gradlew.bat') -Arguments @('-p',$projectRoot,'--version','--no-daemon') | Select-String 'Gradle ' | Select-Object -First 1).ToString().Trim()
    $releaseReady = -not $SkipTests
    $buildReportPath = Join-Path $localApkDir 'BUILD_REPORT.md'
    $notesPath = Join-Path $localApkDir 'RELEASE_NOTES.md'
    if ((Test-Path -LiteralPath $buildReportPath) -or (Test-Path -LiteralPath $notesPath)) { throw 'Build report or Release Notes already exists; refusing to overwrite.' }
    $time = [DateTime]::UtcNow.ToString('o')
    $buildBody = @"
# CarPaly v$versionName local build report

- Build UTC: $time
- Git commit: $expectedCommit
- Git tree: $tree
- Gradle: $gradleVersion
- JDK major: checked during preflight
- Version: $versionName / versionCode $versionCode
- applicationId: $($ledger.applicationId)
- APK: $apkName
- Bytes: $((Get-Item -LiteralPath $apkPath).Length)
- APK SHA-256: $((Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant())
- Signing certificate SHA-256: $($verifyReport.signerCertificateSha256)
- Gradle tests and Lint: $(if ($SkipTests) {'SKIPPED'} else {'PASS'})
- Release signature and package verification: PASS
- Runtime authentication asset pair: PASS (contents never copied to report)
- Source provenance baseline: PASS
- GitHub PR/main CI: see recorded GitHub evidence; not inferred from local build
- Release Draft: not created by the local tool; authenticated main publisher is authoritative
- RELEASE_READY: $(if ($releaseReady) {'YES'} else {'NO'})
- Vehicle and CarPlay behavior: NOT_TESTED
"@
    $notesBody = @"
# CarPaly v$versionName — $($ledger.current.channel)

- Source commit: $expectedCommit
- APK: $apkName
- SHA-256: $((Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant())

Release notes must be reviewed against the version-specific CHANGELOG entry before a Draft is prepared. Real-vehicle features are NOT_TESTED unless evidence for this exact APK is recorded.
"@
    Set-Content -LiteralPath $buildReportPath -Value $buildBody -Encoding UTF8
    Set-Content -LiteralPath $notesPath -Value $notesBody -Encoding UTF8
    Save-State $(if ($releaseReady) {'APK_BUILT'} else {'CANDIDATE_ONLY'}) "apk-sha256=$((Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant()); tests=$(if ($SkipTests) {'skipped'} else {'passed'})" $expectedCommit
    Write-Result 'APK' 'BUILT' $apkPath
    Write-Result 'APK_SHA256' 'INFO' (Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Result 'RELEASE_READY' $(if ($releaseReady) {'YES'} else {'NO'})
    if ($SkipTests) { Write-Result 'APK_LOCATION' 'PRIVATE_CANDIDATE' 'not placed in release-ready directory; RELEASE_READY=NO' }
}
function Invoke-PrepareDraft {
    Write-Phase 'Release Draft 核验'
    $python = Get-PythonPath
    $intent = Get-Content -LiteralPath (Join-Path $projectRoot 'config\release-intent.json') -Raw | ConvertFrom-Json
    if ($intent.enabled -ne $true) { throw 'Release Draft is blocked: release-intent.enabled is false. Only the reviewed authenticated main publisher may create its Tag/Draft.' }
    if ($intent.versionName -ne $versionName -or [int]$intent.versionCode -ne $versionCode) { throw 'Release intent does not match the current ledger assignment.' }
    $branch = (git branch --show-current).Trim()
    $commit = (git rev-parse HEAD).Trim()
    $expectedMainBranch = if ($BuildMainCommit) { $branch -in @('', 'main') -and $commit -eq $BuildMainCommit } else { $branch -eq 'main' }
    if (-not $expectedMainBranch -or @(git status --porcelain).Count -gt 0) { throw 'Draft validation requires a clean, exact main source commit.' }
    $mainSha = (Get-GitValue @('rev-parse','origin/main'))
    if ($commit -ne $mainSha) { throw 'Local main differs from origin/main; refusing draft/source mismatch.' }
    $apkPath = Join-Path $artifactDir $apkName
    if (-not (Test-Path -LiteralPath $apkPath -PathType Leaf)) { throw 'Verified local Release APK is not present at the configured output path.' }
    $releaseIntentResult = & $python (Join-Path $projectRoot 'scripts/release_intent.py') --commit $commit --event push --branch main --conclusion success --main-sha $mainSha 2>&1
    if ($LASTEXITCODE -ne 0 -or (($releaseIntentResult | Out-String) -notmatch 'RELEASE_INTENT_STATUS=READY')) {
        throw 'Reviewed enabled release intent and exact-main CI evidence are required; no tag or draft was created.'
    }
    $runs = Get-GhJson @('run','list','--repo',$repo,'--commit',$commit,'--json','workflowName,status,conclusion,event,headSha')
    $mainCi = @($runs | Where-Object { $_.workflowName -eq 'Android checks' -and $_.event -eq 'push' -and $_.headSha -eq $commit -and $_.status -eq 'completed' -and $_.conclusion -eq 'success' })
    if ($mainCi.Count -lt 1) { throw 'A successful Android checks run for this exact main commit was not found.' }
    $apkPath = Join-Path $artifactDir $apkName
    if (-not (Test-Path -LiteralPath $apkPath -PathType Leaf)) { throw 'Verified local Release APK is not present at the configured output path.' }
    $verificationPath = "$apkPath.verification.json"
    if (-not (Test-Path -LiteralPath $verificationPath -PathType Leaf)) { throw 'APK verification report is missing.' }
    $verification = Get-Content -LiteralPath $verificationPath -Raw | ConvertFrom-Json
    $expectedSigner = Get-CarPalySignerForVersion $ledger $versionCode
    if ($verification.status -ne 'PASS' -or $verification.packageName -ne $ledger.applicationId -or
        $verification.versionName -ne $versionName -or [int]$verification.versionCode -ne $versionCode -or
        $verification.signerCertificateSha256 -ne $expectedSigner) {
        throw 'APK verification evidence does not match current version, package, or signing epoch.'
    }
    $apkHash = (Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksumPath = Join-Path $artifactDir 'SHA256SUMS.txt'
    if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf) -or (Get-Content -LiteralPath $checksumPath -Raw) -notmatch [regex]::Escape($apkHash)) {
        throw 'APK SHA-256 checksum file is missing or inconsistent.'
    }
    $python = Get-PythonPath
    $sourceStatus = & $python (Join-Path $projectRoot 'scripts/release_automation.py') source-check --root $projectRoot --commit $commit 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Release source baseline check failed.' }
    $ghAuth = & gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI authentication is unavailable.' }
    $tagLines = @(& git ls-remote --exit-code origin "refs/tags/$tag" "refs/tags/$tag^{}" 2>&1)
    if ($LASTEXITCODE -ne 0 -or $tagLines.Count -eq 0) { throw 'The verified source tag is missing; local mode is not authorized to create or move tags.' }
    $peeled = $tagLines | Where-Object { $_ -match "\srefs/tags/$([regex]::Escape($tag))\^\{\}$" } | Select-Object -First 1
    $direct = $tagLines | Where-Object { $_ -match "\srefs/tags/$([regex]::Escape($tag))$" } | Select-Object -First 1
    $tagCommit = if ($peeled) { ($peeled -split '\s+')[0] } elseif ($direct) { ($direct -split '\s+')[0] } else { '' }
    if ($tagCommit -ne $commit) { throw 'The remote tag does not point to the exact verified main commit.' }
    $release = Get-GhJson @('release','view',$tag,'--repo',$repo,'--json','tagName,isDraft,isPrerelease,url,body')
    $draftMarker = '<!-- carpaly-release-draft-v1: metadata-only; reviewed-assets-required -->'
    if ($release.tagName -ne $tag -or -not $release.isDraft -or
        [bool]$release.isPrerelease -ne ($ledger.current.channel -eq 'test') -or
        $release.body -notlike "*$draftMarker*" -or $release.body -notlike "*$commit*" -or
        $release.body -notlike "*$expectedSigner*" -or $release.body -notlike "*Android versionCode: $versionCode*") {
        throw 'The authenticated publisher result is not a matching metadata-only Draft.'
    }
    $assetList = Get-GhJson @('api',"repos/$repo/releases/tags/$tag")
    if (@($assetList.assets).Count -gt 0) { throw 'Release Draft contains an asset; no local tool will mutate or upload it.' }
    Write-Result 'LOCAL_APK_SHA256' 'INFO' $apkHash
    Write-Result 'DRAFT_READY' 'VERIFIED' $release.url
    Write-Result 'DRAFT_CREATION' 'WORKFLOW_ONLY' 'local mode never creates/mutates tags or Releases'
    Write-Result 'APK_UPLOAD_REQUIRED' 'YES' 'manual only; never performed by this script'
    Write-Result 'RELEASE_PUBLISHED' 'NO'
}
function Invoke-PrepareGitHub {
    Write-Phase 'GitHub 源码同步与 PR / CI'
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI is missing.' }
    $authOutput = & gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI is not authenticated; no GitHub write was attempted.' }
    $script:githubLogin = (Invoke-Logged -Name '确认 GitHub 操作账户' -Executable 'gh' -Arguments @('api','user','--jq','.login')).Trim()
    if ($script:githubLogin -ne 'Qwy20040320') { throw 'The authenticated GitHub account is not the repository maintainer allowlist; no write was attempted.' }
    $remote = (git remote get-url origin).Trim()
    if ($remote -notmatch '(?i)(github\.com[:/]Qwy20040320/carpaly(?:\.git)?)$') { throw 'origin does not resolve to the approved Qwy20040320/carpaly repository.' }
    Invoke-Logged -Name '刷新 GitHub 远端引用' -Executable 'git' -Arguments @('fetch','origin','--prune') | Out-Null
    $branch = (git branch --show-current).Trim()
    if (-not $branch -or $branch -eq 'main') {
        if ((git rev-parse HEAD).Trim() -ne (git rev-parse origin/main).Trim()) { throw 'A clean main at origin/main is required before creating a new development branch.' }
        $branch = 'codex/carpaly-release-system-' + [DateTime]::UtcNow.ToString('yyyyMMddHHmmss')
        Invoke-Logged -Name '创建隔离开发分支' -Executable 'git' -Arguments @('switch','-c',$branch) | Out-Null
    }
    & git merge-base --is-ancestor origin/main HEAD *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Current branch is stale or unrelated to origin/main; refusing to rewrite or merge history.' }
    Invoke-LocalChecks -IncludeGradle
    $paths = Get-WorkingPaths
    if (@(git diff --cached --name-only).Count -gt 0) { throw 'The Git index already contains staged content; review/commit it before this tool stages anything.' }
    Assert-PublicSafePaths $paths
    $risky = Test-HighRiskChanges $paths
    if ($paths.Count -gt 0) {
        Invoke-Logged -Name '暂存本轮安全路径（逐路径，不用 git add .）' -Executable 'git' -Arguments (@('add','--') + $paths) | Out-Null
        $stagedPaths = @(git diff --cached --name-only | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        if (Compare-Object ($paths | Sort-Object) ($stagedPaths | Sort-Object)) { throw 'The staged file set differs from the reviewed working-tree path set.' }
        Invoke-Logged -Name '检查暂存差异空白与补丁' -Executable 'git' -Arguments @('diff','--cached','--check') | Out-Null
        Invoke-Logged -Name '公开源码树安全检查' -Executable (Get-PythonPath) -Arguments @((Join-Path $projectRoot 'scripts/check_public_tree.py')) | Out-Null
        $gitleaks = Get-Command gitleaks -ErrorAction SilentlyContinue
        if (-not $gitleaks) { throw 'Gitleaks is unavailable; refusing commit and push.' }
        Invoke-Logged -Name '提交前 Gitleaks 检查' -Executable $gitleaks.Source -Arguments @('git','--redact',$projectRoot) | Out-Null
        $staged = (git diff --cached --name-only).Trim()
        if ($staged) {
            Invoke-Logged -Name '创建已审核源码提交' -Executable 'git' -Arguments @('commit','-m',"build: add local release automation ($versionName)") | Out-Null
        }
    }
    $branch = (git branch --show-current).Trim()
    $head = (git rev-parse HEAD).Trim()
    $remoteBranch = & git ls-remote --heads origin $branch
    if ($LASTEXITCODE -ne 0) { throw 'Could not read remote branch state.' }
    if ($remoteBranch) {
        $remoteSha = ($remoteBranch -split '\s+')[0]
        & git merge-base --is-ancestor $remoteSha HEAD *> $null
        if ($LASTEXITCODE -ne 0) { throw 'Remote branch advanced or diverged; normal push stopped without force.' }
    }
    Invoke-Logged -Name '普通快进推送開發分支' -Executable 'git' -Arguments @('push','-u','origin',$branch) | Out-Null
    $pulls = Get-GhJson @('pr','list','--repo',$repo,'--head',$branch,'--base','main','--state','open','--json','number,url,isDraft,headRefOid')
    if (@($pulls).Count -gt 1) { throw 'Multiple open PRs exist for this branch; refusing to choose.' }
    if (@($pulls).Count -eq 1) { $pull = $pulls[0] }
    else {
        $title = "CarPaly $versionName local release system"
        $bodyPath = Join-Path $env:TEMP ("carpaly-pr-" + [guid]::NewGuid().ToString('N') + '.md')
        $body = @"
## 本次内容

- Windows 本地 Release 构建与校验编排、受保护签名预检、版本/源码基线门禁。
- 安全 PR 同步与 GitHub 原生 Auto-merge 条件评估；本 PR 含发布/签名安全高风险改动，保持 Draft 并需人工审查。
- Tag/Release Draft 只核验现有认证发布器结果；不上传 APK、不公开发布、不启用 OTA。

## 验证

- 本地结果由本 PR 对应 Actions 检查记录；所有状态以该提交实际 CI 为准。
- 生产 Keystore 未映射到 PR CI；本地签名凭据不记录在仓库。
- 当前源码/版本若落后于公开 v1.1.56 高水位，Release 构建应失败关闭。

## 高风险审查

- `mobile/build.gradle.kts`、签名 epoch、版本台账及发布工具变更要求人工审核。
- `config/release-intent.json` 保持 disabled。
- 本 PR 不应自动合并。
"@
        Set-Content -LiteralPath $bodyPath -Value $body -Encoding UTF8
        $createArgs = @('pr','create','--repo',$repo,'--base','main','--head',$branch,'--title',$title,'--body-file',$bodyPath)
        if ($risky) { $createArgs += '--draft' }
        $createdUrl = Invoke-Logged -Name '创建 Draft PR（安全改动需要人工审查）' -Executable 'gh' -Arguments $createArgs
        Remove-Item -LiteralPath $bodyPath -Force
        $pullNumber = [regex]::Match($createdUrl, '/pull/(\d+)').Groups[1].Value
        if (-not $pullNumber) { throw 'GitHub did not return a PR number.' }
        $pull = Get-GhJson @('pr','view',$pullNumber,'--repo',$repo,'--json','number,url,isDraft,headRefOid')
    }
    Save-State 'PR_CREATED' "pr=$($pull.number); url=$($pull.url)" $head
    if ($pull.headRefOid -ne $head) { throw 'PR head does not equal the pushed commit; CI result cannot be used.' }
    if ($risky -and -not $pull.isDraft) { throw 'High-risk PR is unexpectedly Ready; no automatic merge is permitted.' }
    Write-Result 'PR' $(if ($pull.isDraft) {'DRAFT'} else {'OPEN'}) "$($pull.url) head=$head"
    $checkOutput = & gh pr checks $pull.number --repo $repo --watch --interval 10 2>&1
    $checkExit = $LASTEXITCODE
    if ($checkExit -ne 0) { Save-State 'GITHUB_FAILED' "pr-checks-exit=$checkExit" $head; throw 'GitHub PR checks failed or did not complete; no merge request was submitted.' }
    $fresh = Get-GhJson @('pr','view',[string]$pull.number,'--repo',$repo,'--json','headRefOid,state,isDraft,mergeable,author,authorAssociation,baseRefName,headRepository,reviews')
    if ($fresh.headRefOid -ne $head) { throw 'PR head changed while checks were running; the newer commit must be checked separately.' }
    Save-State 'CI_PASSED' 'gh pr checks returned success for the exact PR head' $head
    if ($risky) {
        Write-Result 'AUTO_MERGE' 'BLOCKED' 'high-risk workflow/signing/ledger change requires human review; PR remains Draft'
        return [pscustomobject]@{ MainMerged=$false; Reason='HIGH_RISK_PR_REQUIRES_HUMAN_REVIEW' }
    }
    $eligibility = Test-AutoMergeEligibility -PullNumber ([int]$pull.number) -ExpectedHead $head -ChangedPaths $paths
    if (-not $eligibility.Allowed) { Write-Result 'AUTO_MERGE' 'BLOCKED' $eligibility.Text; return [pscustomobject]@{ MainMerged=$false; Reason='POLICY_OR_CI_GATE_BLOCKED' } }
    if ($fresh.isDraft) { Write-Result 'AUTO_MERGE' 'BLOCKED' 'PR is still Draft; no implicit Ready transition'; return [pscustomobject]@{ MainMerged=$false; Reason='PR_REMAINS_DRAFT' } }
    Invoke-Logged -Name '请求 GitHub 原生 Auto-merge（不绕过保护规则）' -Executable 'gh' -Arguments @('pr','merge',[string]$pull.number,'--repo',$repo,'--auto','--merge') | Out-Null
    $mergeCommit = Wait-ForMergedPR -PullNumber ([int]$pull.number) -ExpectedHead $head
    Invoke-Logged -Name '读取合并后的 main' -Executable 'git' -Arguments @('fetch','origin','main') | Out-Null
    $remoteMain = (git rev-parse origin/main).Trim()
    & git merge-base --is-ancestor $mergeCommit $remoteMain *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Verified merge commit is not contained in fetched origin/main.' }
    Save-State 'MAIN_MERGED' "merge-commit=$mergeCommit; origin-main=$remoteMain" $mergeCommit
    Write-Result 'MAIN_MERGE' 'PASS' "mergeCommit=$mergeCommit main=$remoteMain"
    return [pscustomobject]@{ MainMerged=$true; MergeCommit=$mergeCommit; MainCommit=$remoteMain; PullRequestUrl=$pull.url }
}

$selectedModes = @(@($CheckOnly, $SkipTests, $PrepareGitHub, $PrepareDraft, $Status, $FullPrepare) | Where-Object { [bool] $_ })
if ($selectedModes.Count -gt 1 -and -not $FullPrepare) { throw 'Choose one mode at a time; -FullPrepare is the only composite mode.' }
if ($Status) { Invoke-ReadOnlyStatus; exit 0 }
if ($CheckOnly) { $result = Invoke-CheckOnly; exit $result }
if ($PrepareGitHub) { $null = Invoke-PrepareGitHub; exit 0 }
if ($PrepareDraft) { Invoke-PrepareDraft; exit 0 }
if ($FullPrepare) {
    $sync = Invoke-PrepareGitHub
    if (-not $sync.MainMerged) {
        Write-Result 'FULL_PREPARE' 'STOPPED_FOR_REVIEW' $sync.Reason
        exit 0
    }
    $intent = Get-Content -LiteralPath (Join-Path $projectRoot 'config\release-intent.json') -Raw | ConvertFrom-Json
    if ($intent.enabled -ne $true) {
        Write-Result 'RELEASE_INTENT' 'DISABLED' 'No signed Release build or Draft verification will run.'
        exit 0
    }
    $mainSha = (Get-GitValue @('rev-parse','origin/main'))
    if ($mainSha -ne $sync.MainCommit) { throw 'origin/main advanced after the verified merge; rerun checks for the new exact SHA.' }
    $mainCiPassed = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $runs = Get-GhJson @('run','list','--repo',$repo,'--commit',$mainSha,'--json','workflowName,status,conclusion,event,headSha')
        $matching = @($runs | Where-Object { $_.workflowName -eq 'Android checks' -and $_.event -eq 'push' -and $_.headSha -eq $mainSha })
        if ($matching | Where-Object { $_.status -eq 'completed' -and $_.conclusion -eq 'success' }) { $mainCiPassed = $true; break }
        if ($matching | Where-Object { $_.status -eq 'completed' -and $_.conclusion -ne 'success' }) { throw 'Main CI failed for the exact merge commit; local signed build is blocked.' }
        Start-Sleep -Seconds 10
    }
    if (-not $mainCiPassed) { throw 'Main CI did not complete successfully within the bounded wait.' }
    $worktreePath = Join-Path $projectRoot ".private\release-build-worktrees\$mainSha"
    if (Test-Path -LiteralPath $worktreePath) { throw 'The exact-commit private build worktree already exists; inspect it manually before reuse.' }
    $worktreeParent = Split-Path -Parent $worktreePath
    if (-not (Test-Path -LiteralPath $worktreeParent -PathType Container)) { New-Item -ItemType Directory -Path $worktreeParent -Force | Out-Null }
    Invoke-Logged -Name '建立 main 精确提交的隔离 Release 构建 worktree' -Executable 'git' -Arguments @('worktree','add','--detach',$worktreePath,$mainSha) | Out-Null
    $child = Join-Path $worktreePath 'build-release.ps1'
    $powershellExecutable = if ($PSVersionTable.PSEdition -eq 'Core') { Join-Path $PSHOME 'pwsh.exe' } else { Join-Path $PSHOME 'powershell.exe' }
    if (-not (Test-Path -LiteralPath $powershellExecutable -PathType Leaf)) { throw 'A PowerShell executable for the isolated child process is unavailable.' }
    $childArgs = @('-NoLogo','-NoProfile','-File',$child,'-AndroidSdkPath',$AndroidSdkPath,'-PythonExecutable',(Get-PythonPath),'-OutputDir',$artifactDir,'-BuildMainCommit',$mainSha)
    Invoke-Logged -Name '在隔离 main worktree 执行本地 Release 构建与验收' -Executable $powershellExecutable -Arguments $childArgs | Out-Null
    $draftArgs = $childArgs + @('-PrepareDraft')
    Invoke-Logged -Name '只读核验受保护发布器已创建的 Draft' -Executable $powershellExecutable -Arguments $draftArgs | Out-Null
    exit 0
}
Invoke-Build
