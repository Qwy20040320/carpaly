# CarPaly v1.1.51 — 接口提取与 GEELY 适配交付报告

## 结果摘要

版本审计保持 `versionName=1.1.51`、`versionCode=39`、applicationId `com.shihab.diplay.hudtest`。五个用户样本均在本机分析目录找到，已校验文件 SHA-256、Manifest 与签名证书并复用之前生成的 JADX 输出；分析没有执行 APK/Native payload。样本证据支持继续申请正式 ECARX/OneOS SDK，但不足以安全调用任何 Geely OEM 写入或仪表/HUD接口。

没有生成或覆盖 APK，也没有发布标签/Release。永久 Release 签名凭据在本地当前执行上下文不可用；根据项目 Release-only 规范，测试/Debug APK 不得作为用户交付物。

## 验收状态

| 字段 | 状态 | 证据 / 说明 |
|---|---|---|
| `APK_ANALYSIS_STATUS` | `PASS_WITH_LIMITS` | 五个 APK 本地存在；元信息/签名/Manifest 已检查；2 个加固样本及 0914 受保护载荷限制完整代码恢复 |
| `OEM_API_DISCOVERY_STATUS` | `PARTIAL` | 星舱 OneOS Binder 方向盘接口签名和调用点可读；ECARX sensor 调用点、DIM 反射线索可读；OEM grant 未证实 |
| `GEELY_ADAPTER_STATUS` | `BLOCKED` | 没有可证明对普通第三方开放的 Geely OEM API；未增加猜测性适配 |
| `HUD_STATUS` | `BLOCKED` | 2.2 `libgmhud.so` 是应用内部 Native Hook/渲染线索；没有可审计授权 SDK/外部 IPC 契约 |
| `CLUSTER_STATUS` | `PARTIAL` | DIM activation/mode API 名称有样本调用线索；callback/packet schema 和写入权限未知 |
| `STEERING_WHEEL_STATUS` | `PARTIAL` | OneOS listener 声明及样本调用点确认；CarPaly 仍只支持 Android key / 用户学习映射，实车输入未测 |
| `VEHICLE_SENSOR_STATUS` | `BLOCKED` | ECARX 订阅使用方式可见，但 sensor ID 数值、单位、服务授权/天际版支持集未确认；无假油量/车辆数据 |
| `OEM_AUDIO_STATUS` | `UNKNOWN` | 通用 Android AudioTrack/Focus 已有代码；没有 Geely OEM route/AudioPolicy 证据 |
| `RELEASE_SIGNING_STATUS` | `BLOCKED` | 原 Release keystore 文件存在，但当前执行环境无法取得原签名口令；未绕过固定证书指纹 |
| `APK_DELIVERY_STATUS` | `BLOCKED` | 没有本轮签名兼容 Release APK；未生成 Debug/Test 用户包 |
| `VEHICLE_TEST_STATUS` | `NOT_TESTED` | 本轮没有连接 2024 星越 L 天际版或采集 OEM 服务日志 |
| `PR_6_STATUS` | `DRAFT` | 仅允许更新 feature 分支与 Draft PR；不合并 main、不打版本标签、不建 Release |

## 代码变更与测试

- 应用运行时代码没有新增 OEM 调用，CarPlay/QNX、认证链、已发布 v1.1.4 和版本台账均未改动。
- 新增一条共享单元测试，确保 GEELY/KX11 Build fingerprint 即使误开启 BYD 车辆输出，也不能通过 BYD writer gate；原有用户学习映射与 Geely 不套用 BYD 默认键码测试继续保留。
- 按 `AGENTS.md` 完成完整 Gradle CI：`BUILD SUCCESSFUL in 1m 40s`。shared/common 的 JUnit XML 共 2,029 项，2,026 通过、3 跳过、0 失败/错误；home 单元测试任务无 XML 测试报告。mobile/home/maphost 的 lint 和三模块 Debug assemble 任务全部成功。mobile lint 报告 0 错误、18 条警告；home/maphost 本次无可读 lint 报告，不额外声称警告数量。
- `scripts/android_versioning.py check`、`scripts/check_project_docs.py`、版本台账/发布流水线单测（19 项，6 项因 Windows 不执行 Bash 专项而跳过）、workflow immutable-action pin 检查均通过；`scripts/check_public_tree.py` 在将七份明确白名单文档暂存后通过。此测试只验证软件安全门，不证明真实方向盘/HUD/音频功能。

## 必须明确的未完成项

1. 2024 天际版实车的 OneOS 服务、系统签名权限、ECARX Sensor grant、DIM 服务和 audio route 均无动态证据。
2. 当前没有 Geely HUD/Cluster/Sensor/OneOS adapter，不把 BYD 输出代码改名为 Geely。
3. Release signer口令需要由授权者在安全的本机环境恢复到既定签名配置；不在聊天、终端输出或仓库中传递。
4. 必须提供 ECARX/Geely 官方 SDK 或正式接口说明，包含目标固件、permissions/protectionLevel、可用安装身份及明确 read/write 契约，才能实现下一步 adapter。
5. 所有车辆验证均需用户在安全驻车状态完成；测试失败或服务拒绝时应显示 Unknown/Unavailable，不得合成车值或写车控总线。
