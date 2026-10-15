# CarPaly Android Release 签名策略

所有用户 APK 必须来自 Android `release` variant，包名固定为 `com.shihab.diplay.hudtest`，文件名固定为 `CarPaly-XingyueL-v{versionName}.apk`。不得交付 Debug/Test/Upgrade-Test 构建，不得生成新 Keystore 代替历史身份，不得覆盖已交付 APK，也不得通过卸载或清数据绕过签名不兼容。

## 已验证的签名 epoch

版本台账 `config/android-version-ledger.json` 中的 `signingEpochs` 是逐版本签名身份的机器可读来源。versionCode 41+ 使用活动身份：

| versionCode | SHA-256 证书指纹 | 状态 | 依据 |
| ---: | --- | --- | --- |
| 36–40 | `4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90` | 历史 | v1.1.4 / v1.1.5 历史发布及 v1.1.51 / v1.1.52 APK 核验；v1.1.52 GitHub Release 的频道正文冲突与缺少验证侧车须单独披露 |
| 41+ | `d9b329525fc1ef21c365fab72c10367527cc038297c4f30eaa22b2207429139e` | 当前 | 已下载并用 Android SDK `apksigner` 验证的公开 v1.1.53、v1.1.54、v1.1.56 APK |

该切换不重写历史资产。不同 epoch 的证书指纹不同，因此不得声称 code 40 安装可直接升级 code 41+；除非 Android 签名谱系/轮换证明或目标设备覆盖安装测试实际通过，否则标记 `UPGRADE_COMPATIBILITY=NOT_TESTED`。`v1.1.55/code43` 没有可核实的源码 Tag/Release，状态为 `SOURCE_UNVERIFIED`，不作为构建基线。

## 凭据和预检

本地 Release 需要 `ANDROID_KEYSTORE_PATH`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD` 和本地授权的运行时认证资源。值不能写入源码、命令行字面量、日志、报告或 Git。构建前运行 `:mobile:verifyCarPalyReleaseSigning`；Gradle 从版本台账为当前 versionCode 选取唯一 epoch，并校验证书和私钥可用。GitHub 的 `RELEASE_SIGNING_CERT_SHA256` 只允许匹配活动 epoch；签名 Secret 仅能在受保护发布环境中访问，PR/普通 CI 不映射生产凭据。

缺失或不匹配时必须失败关闭。不要猜密码、破解/绕过 DPAPI、生成替代 Keystore、修改指纹来迁就错误凭据或回退到 Android Debug 密钥。凭据不可用时报告 `BLOCKED_BY_SIGNING`。

## 本地构建和验收

使用 `build-release.ps1` 做环境预检与本地构建；底层 `scripts/build-release-apk.ps1` 仍负责 Release 变体、APK 完整性、签名、版本和运行时资源校验，并拒绝覆盖既有产物。`-SkipTests` 只生成 `.private` 下的非就绪候选，`RELEASE_READY=NO`，不能进入发布目录。`-CheckOnly` 不生成 APK。不要把 Android APK 签名与 CarPlay/MFi 认证材料混为一谈。

当前已知公开 APK 包含 `assets/offline-mfi/identity.pk8` 和 `certificate.p7b` 资源名。公开仓库/Release/Pages/Actions Artifact 不得由本地发布工具上传 APK。认证材料公开分发权仍需独立授权审查；本策略不声称已经完成法律审核，也不以公开证书指纹替代私钥控制。

正式发布仍只能在目标源码合入 main、CI 通过、版本台账合法、同一 main 提交明确启用并变更 `config/release-intent.json` 后由受保护的认证发布器准备 metadata-only Release Draft。Draft 必须保持 `draft=true`、无附件；本地脚本不上传 APK、不点击 Publish、不启用 OTA，也不修改已发布 Release。

## 必需门禁

CI may build Debug internally, but **no Debug APKs** are user-deliverable. Every user APK must use the Release variant and its version-code signing epoch.

- `SIGNING_EPOCH_MATCH`：versionCode 只映射到台账中的一个 epoch，且 Keystore/APK 证书一致。
- `PACKAGE_NAME_MATCH`：包名固定且无 suffix。
- `VERSION_CODE_INCREMENT`：版本高于完整历史高水位；来源提交是最新已验证发布源码的后代。
- `RELEASE_SIGNED_APK`：Release variant、`debuggable=false`、`apksigner` 验证通过。
- `SENSITIVE_FILE_SCAN`：Keystore、密码、认证材料、APK 和私有诊断文件不得进入 Git 或公开自动化资产。
- `USER_DATA_PRESERVATION`：除非获准设备完成覆盖安装及设置恢复测试，否则为 `NOT_TESTED`。
- `VEHICLE_VALIDATION`：构建与模拟测试不等于真实 iPhone/星越 L 验收。
