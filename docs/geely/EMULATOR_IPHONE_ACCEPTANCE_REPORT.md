# CarPaly V9.3 模拟器与 iPhone 接入验收报告

日期：2026-10-10

范围：本地 Android 模拟器验收、认证资源分层验证、iPhone 接入条件评估。本文已脱敏；原始系统日志、诊断 ZIP、模拟器截图及 APK 均不随本报告提交。

## 状态摘要

| 项目 | 状态 | 结果 |
| --- | --- | --- |
| 模拟器安装与启动 | PASS | Android 16 / API 36、x86_64 AVD；CarPaly 1.1.4 安装并启动。 |
| 中文界面 | PASS | Android `zh-CN`（配置显示 `zh-rCN`）；CarPaly 配对说明、首次车辆设置及连接设置页面均显示中文。模拟器保持普通可见窗口运行。 |
| 单元测试 | PASS | 2,018 项；2,015 通过、3 跳过、0 失败、0 错误。包含 `home` 模块 4 项返回键测试。 |
| Android Lint | PASS_WITH_WARNINGS | 18 条 Warning、0 Error；详情见下文。 |
| APK 结构与签名 | PASS | 本地测试 APK 包名、版本及 v2 调试签名检查通过；不代表正式发布签名。 |
| 诊断与日志 UI | PASS | 手动日志开关、持久化、查看、清除、轮转限制信息和 ZIP 导出已在模拟器检查；本轮测试数据已清理，上传仍需用户主动操作。 |
| 本地 MFi 资源读取/挑战签名探针 | PASS（仅本地） | 安装 APK 中存在离线资源；应用进程内探针完成 6 次本地签名、0 次远端请求。运行态仍标记 `LOADED_NOT_TRUSTED`。 |
| iPhone USB / 无线 CarPlay | BLOCKED / NOT_TESTED | Windows 能枚举已连接的 iPhone，但 Android AVD 的 USB Host 未见该设备；模拟器网络为虚拟 NAT，且 AVD 无法直通宿主机 iPhone / 蓝牙硬件。没有完成真实 iPhone 握手。 |
| 星越 L 实车、原车音频、Siri、麦克风 | NOT_TESTED | 未连接真实车机，不能据模拟器结果宣称车辆功能可用。 |

## 环境与安装包

- 模拟器：`CarPaly_API36_x86_64`，Android 16 / API 36，当前 AVD 窗口可见运行。
- 语言：`persist.sys.locale=zh-CN`，Android 资源配置包含 `zh-rCN`。
- 测试包：`com.shihab.diplay.hudtest`，`versionName=1.1.4`、`versionCode=36`、`targetSdk=37`。
- 已安装的本地认证测试 APK：22,691,300 字节；SHA-256 `8ADE4913F071E955CBE6F7E9FD54EAE92C847F8645945F231FA89C917796EFA4`。Android v2 签名验证通过，使用调试证书；不是生产签名包。
- 独立 CI 构建的无认证资源 APK：22,446,797 字节；SHA-256 `D4FD0CF981C349C630D78FACAEA0497E229FE858FE4AD198DE42724A5E013E34`。该包与安装测试包不同，不应覆盖模拟器中的本地认证测试包。
- APK 包名、内部版本、目标 SDK、ZIP/APK 结构和 v2 签名均已检查。APK 仅留在本机忽略目录，不在本报告中分发。

## 自动化构建与静态检查

- Gradle 单元测试汇总：`shared` 1,035 项；`common` 979 项，其中 3 项跳过；`home` 4 项；合计 2,018 项、2,015 通过、0 失败、0 错误。
- Lint：`mobile` 报告 18 条警告、0 错误：14 条 `SetTextI18n`、2 条来自转换后依赖类的 `TrustAllX509TrustManager`、1 条 `UnusedAttribute`（`localeConfig` 的 minSdk 提示）、1 条 `UnusedResources`。警告并未被当作实车验证或安全审计通过；信任所有证书的依赖告警仍需单独确认来源和影响。
- 首次标准打包时，Windows 报告目标 APK 正被 Bandizip 占用，`:mobile:packageDebug` 无法写入。未结束或关闭该用户进程；随后将 Gradle `:mobile` 输出重定向到忽略的本机临时目录。完整 CI 命令最终 **BUILD SUCCESSFUL**：248 个 actionable tasks（27 executed、221 up-to-date），包括三模块单元测试、Lint 和 APK 构建。最终诊断 APK 完成结构、版本和 v2 签名验证，签名类型为调试证书；APK 不含离线 MFi 认证资源。
- 可见 AVD 上执行多轮应用启动观察；最终首页/连接设置页面可打开，诊断页面和设置入口可用。观察期间未见 FATAL EXCEPTION 或 ANR。应用重启观察不是长时间稳定性测试。

## 诊断与日志检查

- 日志保持默认关闭；手动打开后能查看实时/历史内容，再关闭并重启应用，关闭状态仍持久化。
- UI 显示单文件 5 MB、总量 50 MB、保存 7 天、最多 20 个文件的限制；可显示保存路径、文件数量与占用空间。
- 手动清除后，本轮模拟器日志计数为 0；成功生成 ZIP，并检查 ZIP 结构及脱敏结果（未发现本轮扫描规则命中的敏感字段）。
- ZIP 与运行日志只在本机生成；没有上传到 GitHub 或发送到外部服务。

## iPhone 接入结论

- Windows 即插即用设备列表中出现 Apple iPhone；本报告不记录设备序列号、网络名称或 IP 地址。
- ADB 侧只有 Android 模拟器；模拟器 `UsbManager` 状态为 `NO_DATA`，无已授权 iPhone USB 设备。Windows 检测到 iPhone 不等于 Android AVD 获得 USB 透传。
- 用户说明 iPhone 已连接电脑 USB 且与电脑处于同一局域网。此条件仍不足以完成模拟器内的 CarPlay 对等链路：AVD 使用虚拟 NAT 网络，未获得真实 iPhone USB 与蓝牙/P2P 硬件通道。
- 因此有线握手、无线握手、Apple 信任授权、原车音频、Siri、麦克风全部标记 **NOT_TESTED**；没有发送 CAN/UDS 或车身控制命令。单元测试与本地签名探针不等于真实认证成功。

## 后续实车验证

在车辆安全停车状态下，由用户将测试 APK 安装到 2024 星越 L 天际版车机并使用真实 iPhone 测试。分别记录：有线信任提示与握手、无线配对、视频、原车音频焦点、Siri 收发音、麦克风输入、方向盘按键、倒车/360 优先级及 HUD。用户确认后再导出诊断 ZIP；提交前检查并脱敏。任一未实测项目在取得证据前均保持 `NOT_TESTED`。

## 可复现检查脚本

仓库脚本 `scripts/Test-CarPalyEmulator.ps1` 仅检查已启动的 AVD、中文 locale、已安装包版本并将 CarPaly 主界面带到前台；默认不重启进程。它不启动隐藏模拟器、不安装或替换 APK、不清除应用数据、不读取/上传日志，也不发出车辆控制命令。
