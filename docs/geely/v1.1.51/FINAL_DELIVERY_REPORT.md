# CarPaly v1.1.51 — 七 APK 适配与本地 Release 构建报告

## 结论

本轮完成七个用户提供 APK 的静态证据汇总、一个只读车辆数据模型和音频路由诊断日志，并生成了本地固定签名 Release APK。`v1.1.51` 保持 `versionName=1.1.51`、`versionCode=39`、`applicationId=com.shihab.diplay.hudtest`。本 APK 是本地测试交付物，不代表实车功能已经通过；没有创建版本标签、GitHub Release，也没有公开上传 APK 或认证材料。

本轮未实现 Geely 专有 HUD、仪表、方向盘、燃油或音频服务适配。样本中发现的系统组件、内部 Native Hook、反射字符串和第二屏路径不足以证明第三方应用有权调用 OEM 服务。

## 验收状态

| 字段 | 状态 | 证据 / 说明 |
|---|---|---|
| `APK_ANALYSIS_STATUS` | `PASS_WITH_LIMITS` | 七个 APK 的已有报告与本轮两份新增样本分析相互参照；分析限于静态材料，未执行 APK 或 Native 载荷 |
| `OEM_API_DISCOVERY_STATUS` | `PARTIAL` | 少量 OneOS listener、ECARX sensor 调用点和 DIM 反射线索可读；权限、服务契约、目标固件可用性未证实 |
| `GEELY_ADAPTER_STATUS` | `PARTIAL_READ_ONLY_MODEL` | 新增有来源、单位、有效期与安全边界的通用只读数据模型；未接入车辆服务、CAN、UDS 或 Vehicle HAL |
| `HUD_STATUS` | `NOT_IMPLEMENTED` | Fake Ultra 的 Android 第二显示器 Surface 路径不是星越 L OEM HUD API 证据 |
| `CLUSTER_STATUS` | `NOT_IMPLEMENTED` | 样本中的 DIM 名称/反射线索缺少可信公开契约与权限证据 |
| `STEERING_WHEEL_STATUS` | `NOT_TESTED` | 保留 Android 媒体按键转发路径；无星越 L 方向盘事件实车验证 |
| `VEHICLE_SENSOR_STATUS` | `NOT_IMPLEMENTED` | 数据模型可以表示速度/燃油/RPM 等只读值，但未连接传感器提供方；未显示伪造车辆数据 |
| `OEM_AUDIO_STATUS` | `NOT_TESTED` | 增加隐私受限的音轨状态日志，不改变现有音频路由；不能据此证明导航语音或原车音频已修复 |
| `RELEASE_SIGNING_STATUS` | `PASS` | v2 APK 签名有效；证书 SHA-256 与固定签名身份一致：`4d26d1c861b41a2cee4515e31f5f5c7eb13b9dd06e7485aa1687bc1d2ac73d90` |
| `AUTH_ASSET_STATUS` | `PASS_LOCAL_ONLY` | Release 构建包含本地 `identity.pk8` 和 `certificate.p7b`；PKCS#8/证书解析、配对与 APK 内输入一致检查通过。私钥可从 APK 提取，因此文件仅留在本机，不公开分发 |
| `APK_DELIVERY_STATUS` | `LOCAL_RELEASE_BUILT` | 本地路径 `artifacts/CarPaly-XingyueL-v1.1.51.apk`；未创建 GitHub Release |
| `AUTOMATION_STATUS` | `PASS` | shared/common 共 2,035 个测试条目：2,032 通过、3 跳过、0 失败；home 没有 XML 测试报告。Lint 与三个模块 Debug assemble 通过 |
| `PR_6_STATUS` | `DRAFT` | 代码推送到现有功能分支并更新现有 Draft PR；不合并 `main` |
| `VEHICLE_TEST_STATUS` | `NOT_TESTED` | 本轮没有接入真实 iPhone 或 2024 星越 L 天际版进行 CarPlay、音频、HUD、仪表或方向盘测试 |

## APK 信息

- 文件：`artifacts/CarPaly-XingyueL-v1.1.51.apk`
- 构建类型：Android Release variant，非 Debuggable
- 包名 / 版本：`com.shihab.diplay.hudtest` / `1.1.51` / versionCode `39`
- 最低 / 目标 API：25 / 37；包含 `arm64-v8a`、`armeabi-v7a`、`x86`、`x86_64`
- 大小：16,963,656 字节
- SHA-256：`222801dbc5e96b668c22a078da38d2b4ed184724c0b088c35d7d04c32752754a`
- 签名：Android v2 有效；固定证书指纹与项目固定值相符
- APK ZIP 完整性、包名、版本、非 Debuggable、认证资源与本地输入一致、Native ABI 和版本不可变检查：均通过
- APK 内嵌源码标识：`ee7a6afd675d`。之后的提交仅更新版本台账、发布说明和本地构建产物忽略规则，不改 APK 中的应用源码。

对应机器生成检查记录：`artifacts/CarPaly-XingyueL-v1.1.51.apk.verification.json`；校验值 sidecar：`artifacts/CarPaly-XingyueL-v1.1.51.apk.sha256`。整个 `artifacts/` 目录均为本地构建产物，不提交 Git。

## APK 静态分析摘要

- Fake Ultra：Android 第二显示器选择、DisplayListener 与 Surface 生命周期有可读调用路径；“HDMI2”日志字符串不证明物理端口映射，也不证明可调用 Geely DIM/HUD。JADX 部分反编译失败，结论仅采用能由字节码和资源交叉确认的部分。
- Glauncher：通用 Android 启动器/包广播组件，没有确认到 CarPlay、ECARX、OneOS、DIM、HUD 或车辆传感器集成。
- 五个先前样本：沿用已生成的分析与接口矩阵，不重新执行全量 JADX。Star Cabin 提供部分 OneOS/ECARX/DIM 调用线索，但安装身份、权限授予、参数语义和目标天际版可用性仍未知；其他样本中的内部 Native/受保护调用不作为可复用公共 API。
- 未执行反编译产物中的 APK、动态库、脚本或注入载荷；静态字符串不作为方法签名、权限或运行能力的证明。

## 代码与自动化验证

- 增加 `GeelyVehicleData` 只读类型，携带来源、单位、采样时间、有效性及过期边界；异常或权限缺失时不提供伪造值。范围检查是防御性校验，不是吉利规格。
- 增加六个车辆数据模型单元测试。
- 在现有 Android 音频轨道启动后记录类型、声道、播放状态、用途、路由设备类别与 underrun 计数；不记录设备名称/地址或音频内容，不更改音频焦点和路由选择。
- Release 脚本可显式指定 Python，跳过 Windows Store 的 `python.exe` 执行别名，并让签名 Gradle 任务使用 `--no-daemon`。
- 完整 CI 命令成功：`BUILD SUCCESSFUL`。mobile lint 为 0 fatal、0 error、18 warning；home/maphost lint 与三模块 Debug assemble 均通过。
- `scripts/android_versioning.py check`、`scripts/check_project_docs.py`、版本/发布脚本测试及 workflow action pin 检查通过。发布脚本测试共 11 项，其中 6 项 Bash 专项在 Windows 跳过。
- Gitleaks 与公开源码树检查通过；认证文件、签名 Keystore、APK 和授权截图未加入 Git。

## 未完成 / 阻塞

1. 没有 Geely/ECARX 官方 SDK 或授权 API 文档来确认服务名、签名权限、目标固件支持及参数契约；因此不实现 OEM HUD、仪表、方向盘、传感器或音源写操作。
2. 导航语音无声、原车顶部系统栏遮挡、自动重连、CarPlay 触控、Siri、麦克风和车载音频的实车回归仍待用户提供结果。新诊断字段只能辅助采集，不能算修复验证。
3. 认证资源虽通过技术校验，聊天截图只是用户提供的授权沟通材料；截图中的账号与 DiPlay 原作者身份以及授权方对这组材料的再授权权利没有独立核实。包含私钥的 APK 暂不公开发布。
4. 2024 星越 L 天际版及其他年型的实车状态全部保持 `NOT_TESTED`。不得把模拟器、单元测试或用户早期的单车反馈外推为本轮验收。

## Git 与发布状态

- 工作分支：`feature/carpaly-v1.1.5`
- 最新代码提交：`ee7a6afd675deb3a02c6c35ac870eef32899f9ba`
- 更新范围：原有 Draft PR #6；未合并 `main`、未创建版本标签、未创建或更新 GitHub Release。
- 本地 APK 仅供在用户知情下进行签名兼容性与车机测试；在授权身份/范围获得独立核验前，不作为公开下载文件。
- 本地诊断采集脚本的既有用户修改保持未暂存、未提交。
