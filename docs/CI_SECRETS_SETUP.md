# CarPaly 历史版本构建与签名环境说明

本文说明 `.github/workflows/carpaly-android-build.yml` 的构建边界。当前只准备构建及验签流程；不会创建 Tag、Release、上传 APK、启用 OTA 或更改任何线上 Secret。

## GitHub Environment

仓库管理员可在 `Settings → Environments` 查看 `mfi-public-release`。现有流程应继续限制为受保护的 `main` 分支及经审核的版本标签，并保留现有审核规则。不要让 PR、Fork PR 或任意开发分支取得发布凭据；不要为了本工作流放宽 Environment 保护。

工作流所使用的 Environment Secrets 名称（只检查名称，不显示值）为：

| Secret | 用途 |
| --- | --- |
| `RELEASE_KEYSTORE_BASE64` | 原 Android Release PKCS#12 文件的 Base64 编码 |
| `RELEASE_STORE_PASSWORD` | PKCS#12 容器密码 |
| `RELEASE_KEY_ALIAS` | 已有签名私钥条目的 alias |
| `RELEASE_KEY_PASSWORD` | 对应私钥条目的密码 |
| `MFI_IDENTITY_PK8_BASE64` | CarPlay 运行时认证输入；不是 Android APK 签名密钥 |
| `MFI_CERTIFICATE_P7B_BASE64` | 配套运行时认证证书；不是 Android APK 签名证书 |

Environment Variable `RELEASE_SIGNING_CERT_SHA256` 是公开证书 SHA-256 指纹，不是 Secret。指纹检查区分 Android APK 签名身份与 MFi 运行时认证材料。

截至本次只读检查，`mfi-public-release` 的指纹变量为旧身份 `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90`；历史 V1.1.54 和 V1.1.56 源码、APK 台账要求 `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e`。因此签名候选作业会在读取或映射任何签名 Secret 之前失败关闭。Secret 名称存在不代表其内容、alias、密码或证书已验证。本任务不会更改这一配置；不能通过改指纹来绕过不匹配。

## 本地准备文件

请只从已授权的签名材料备份读取文件；不要把 Keystore、密码、PKCS#8、P7B 或 Base64 临时文件放入仓库、日志、构建缓存或公开 Artifact。PowerShell 可在内存中编码文件，并将编码通过标准输入直接交给 GitHub CLI；不要把编码写入屏幕或命令参数：

```powershell
$keystorePath = 'C:\protected\CarPaly\release.p12'
$bytes = [System.IO.File]::ReadAllBytes($keystorePath)
try {
    [Convert]::ToBase64String($bytes) | gh secret set RELEASE_KEYSTORE_BASE64 --repo Qwy20040320/carpaly --env mfi-public-release
} finally {
    [Array]::Clear($bytes, 0, $bytes.Length)
    Remove-Variable bytes
}
```

只有在获批更新生产环境后才执行 Secret 写入。密码应在 GitHub Environment 的 Secret 输入框中单独录入，不要放入脚本、PowerShell 命令参数、环境文件或历史记录。上例不应在本轮照做；它只是受控维护操作的安全模式示例。

## 手动检查与运行

1. 打开仓库 `Settings → Environments → mfi-public-release`，只核对 Secret 名称和 Variable 名称，不复制、回显或导出值。
2. 确认该 Environment 的分支/标签规则和审核人仍符合组织发布策略。
3. `Actions → CarPaly historical Android builds → Run workflow` 可在受保护的 `main` 上选择版本与 `verify` 或 `release`。`verify` 不读取签名凭据；`release` 才会进入受保护签名环境。
4. 在执行签名候选前，先人工核对所选源码提交、该版本的签名政策，以及 Environment pin。签名候选作业必须先通过指纹预检，再映射 Secret。
5. 检查 Run 的每个 Job 和步骤。成功的 APK 检验报告会记录来源提交、版本、包名、文件哈希和签名验证状态，不包含凭据。
6. 只有不含敏感运行时认证材料的日志/测试报告才允许作为短期 Artifact；本工作流不上传 APK。公开仓库中的 Actions Artifact 不能当作私有文件柜。

历史版本映射位于 `config/ci-rebuild-sources.json`。V1.1.54 与 V1.1.56 当前各绑定到一个已核实提交；V1.1.55 标为 `SOURCE_UNVERIFIED`，故其构建请求必须失败。修复它需要可审计的原始构建来源证据，并经代码审查更新映射；不能把其他版本的源码改个版本号来代替。

## 分发与草稿 Release

三份本地 APK 均含有 `assets/offline-mfi/identity.pk8`。这类 APK 不得上传到公开 GitHub Release、Pages、Actions Artifact 或 OTA Feed。本工作流最多上传不含 APK 的验证报告，不创建或更改 Release。只读检查时 V1.1.54 与 V1.1.56 Release 已是正式发布状态且已有 APK 附件；本工作流不会覆盖或修改它们。V1.1.55 暂无 Release，且来源未确认。

如果生产签名证书、Environment pin 与目标版本策略不一致，停止构建并由仓库管理员先审查签名时代/Environment 设计。不得改用 Debug 签名、换 Keystore、复用另一时代的 pin，或放宽分支保护。
