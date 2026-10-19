# CarPaly

### Geely Xingyue L / KX11 CarPlay Receiver

[![Android CI](https://github.com/Qwy20040320/carpaly/actions/workflows/android.yml/badge.svg?branch=main)](https://github.com/Qwy20040320/carpaly/actions/workflows/android.yml)
[![GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
![Android](https://img.shields.io/badge/Android-API%2025%2B-green)

> 中文为主 · English summary below。CarPaly 是社区开发中的 Android CarPlay 接收端项目，不是吉利、ECARX、Apple 或任何车机厂商的官方软件。

## 项目简介

CarPaly 基于开源项目 DiPlay 持续开发，重点为吉利星越 L（内部代号 KX11）提供一个可审慎选择的接收端配置，并完善只读诊断、可控日志和开发者构建流程。2024 天际版是当前优先验证目标。

车型配置、协议代码或自动化测试通过，都不等于所有年款已经兼容。用户曾反馈 v1.1.4 在一辆星越 L 上连接 CarPlay、音乐可播放；另一次近期反馈称连接、Siri 双向语音和方向盘按键有响应，但音乐会自动暂停、导航播报无声、顶部原车状态栏仍遮挡画面。后一次测试包版本及有线/无线模式未记录，维护者也未独立复测；不能把单车反馈外推为全系支持。

## 官网与车机在线更新

目标官网：[https://qwy20040320.github.io/carpaly/](https://qwy20040320.github.io/carpaly/)（本分支已准备双语站点与 Pages 工作流；远端 Pages 尚未启用，部署状态请以 GitHub Pages 设置和 Actions 为准）。

Stable/Beta OTA 客户端与签名清单生成器正在开发。生产验签公钥和签名环境尚未配置，因此当前应用不会信任或下载 OTA 更新；v1.1.51 也不代表已包含本分支的 OTA 实现。不会自动下载或静默安装，Android 系统始终要求用户确认。没有可信驻车传感器时，安装器只会在用户明确确认安全停车且 CarPlay 已停止后打开。

## Windows 本地 Release 工具

仓库提供 [`build-release.ps1`](build-release.ps1) 作为统一入口：`-Status` 只读查看状态，`-CheckOnly` 只做环境/版本/来源/签名预检，默认模式运行 Release 构建与验收；`-PrepareGitHub` 只同步已审查的源码并等待 PR CI，`-PrepareDraft` 只核验受保护发布器创建的 metadata-only 草稿。它不会上传 APK、创建或移动 Tag、公开 Release 或启动 OTA。当前版本台账落后于公开 code 44 高水位，原签名凭据在本机也未配置，因此预检会失败关闭；不得用 Debug 或新密钥代替。详见[本地发布指南](docs/LOCAL_RELEASE_GUIDE.md)。

## 当前发布状态

以下发布信息从 GitHub Releases、标签、资产校验记录与本地版本台账生成。只有实际发布的 Release 才提供公开下载链接；本地候选版本不会被显示为已发布版本。

版本状态摘要：v1.1.4 为历史公开版，v1.1.5 为历史预发布，v1.1.51 为已登记交付，v1.1.52 的 Release 正文状态存在冲突且 APK 资产尚未验证。v1.1.6 是规划中的版本标签，当前未分配、未发布；版本分配仍受版本台账高水位约束。

<!-- CARPALY:RELEASES:START -->
### GitHub 发布状态（自动同步）

GitHub 最新正式 Release：[v1.1.56](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.56)，发布于 2026-10-15。该 Release 暂无可验证 APK 下载附件。 APK 验证状态：`NOT_VERIFIED`。
**说明状态冲突：** GitHub 将该 Release 标记为正式版，但人工说明仍写有预发布措辞；自动同步保留原说明，不擅自改写。

最近已发布的版本：

| 标签 | 类型 | 日期 | APK 附件 | 源码提交 |
| --- | --- | --- | --- | --- |
| [v1.1.56](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.56) | 正式 | 2026-10-15 | 有 APK 附件（未验证，不提供链接） | `6b206c9e6944` |
| [v1.1.54](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.54) | 正式 | 2026-10-15 | 有 APK 附件（未验证，不提供链接） | `e3eca1dc5145` |
| [v1.1.53](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.53) | 正式 | 2026-10-14 | [CarPaly-XingyueL-v1.1.53.apk](https://github.com/Qwy20040320/carpaly/releases/download/v1.1.53/CarPaly-XingyueL-v1.1.53.apk) | `64703e7dced8` |
| [v1.1.52](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.52) | 正式 | 2026-10-13 | 有 APK 附件（未验证，不提供链接） | `64703e7dced8` |
| [v1.1.51](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.51) | 正式 | 2026-10-11 | 有 APK 附件（未验证，不提供链接） | `ef8bec6e0d20` |
| [v1.1.5](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.5) | 预发布 | 2026-10-11 | 有 APK 附件（未验证，不提供链接） | `ef8bec6e0d20` |
| [v1.1.4](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.4) | 预发布 | 2026-10-11 | 有 APK 附件（未验证，不提供链接） | `ef8bec6e0d20` |
<!-- CARPALY:RELEASES:END -->

### 当前候选版本

<!-- CARPALY:CANDIDATE:START -->
**本地候选：v1.1.57 / versionCode 45。** 尚无公开 Tag、Release 或下载链接。本地 APK 的哈希、版本和 d9 签名可核验，但它与整合后源码提交的可复现对应关系尚未建立。真实车辆功能仍为 NOT_TESTED；OTA 未启用。
<!-- CARPALY:CANDIDATE:END -->

### 近期实车反馈（用户报告，非维护者复测）

<!-- CARPALY:VEHICLE_FEEDBACK:START -->
| 功能 | 近期实车反馈 | 证据说明 |
| --- | --- | --- |
| CarPlay 连接 | 用户反馈通过（未独立复现） | 用户反馈连接正常；测试 APK 版本、车型配置及有线/无线模式未记录，维护者未独立复现。 |
| 音乐播放 | 用户反馈问题 | 用户反馈音乐播放约一秒后自动暂停；唤醒 Siri 时音乐可播放。 |
| 导航语音 | 用户反馈失败 | 用户反馈导航提示音无声；根因及修复状态尚未由本轮新实车复测确认。 |
| Siri 双向语音 | 用户反馈通过（未独立复现） | 用户反馈可听见 Siri 且 Siri 能听见用户；未独立复现。 |
| 方向盘按键 | 用户反馈通过（未独立复现） | 用户反馈按键有响应；具体按键与映射未记录，未独立复现。 |
| 顶部原车状态栏 | 用户反馈失败 | 用户反馈仍遮挡 CarPlay 画面。 |
| HUD、仪表与燃油数据 | NOT_TESTED | 没有可核实的实车接口调用或验收证据。 |

以上是用户反馈，不等于维护者验证；测试 APK 版本和连接模式未记录的结果不会外推到全系车型。
<!-- CARPALY:VEHICLE_FEEDBACK:END -->

## 项目定位与目标

- 在 Android 车机上运行 CarPlay 接收端；保留 DiPlay 已有的 USB、网络、音视频接收代码。
- 根据明确的 Geely/ECARX 与 KX11 身份证据选择接收端配置；分辨率本身不会被当作车型证据。
- 优先验证星越 L 2024 天际版，同时保留 2021–2026 年型和 KX11 Generic 候选配置。
- 通过诊断中心帮助用户安全采集本机连接状态；不访问未经授权的车辆总线或私有车机服务。
- 只在取得公开、可验证的接口依据并完成安全评估后，考虑扩展车机集成。

本项目不是 Apple、MFi、吉利或 ECARX 官方软件，不声称取得 Apple 配件认证或 MFi 认证。公开源码不提交认证私钥；个别二进制是否包含运行所需认证资源，以对应 Release 的实际构建和说明为准，嵌入 APK 的资源可能被提取。

## 与 DiPlay 的关系

CarPaly 是 [shihabal3amri/DiPlay](https://github.com/shihabal3amri/DiPlay) 的社区派生项目，保留原项目要求的 GPL-3.0 许可与版权声明，并在此基础上开发 KX11 候选适配、诊断和日志功能。原项目远程仍作为开发参考；详见下方许可证与致谢。

## CarPaly 独立版本体系

CarPaly 使用自己的版本序列：`1.1.1 → 1.1.2 → 1.1.3 → 1.1.4 → …`。每次发布递增末尾数字，例如 `1.1.9` 之后是 `1.1.10`；DiPlay 上游版本只用于源码跟踪和移植，不会改变 CarPaly 的应用版本。

| 历史标签（仅作版本映射） | CarPaly 展示映射 | 实际 APK 元数据 | 当前状态 |
| --- | --- | --- | --- |
| `v0.1.0`（已清理） | `v1.1.1`（仅映射） | `versionName=0.2.15-hud-test`，`versionCode=34`，`com.shihab.diplay.hudtest`，Android Debug 签名 | Release 与 Git 标签已从 GitHub 删除；APK 仅保存在本地忽略备份目录，不提供公开下载 |
| `v0.1.1`（已清理） | `v1.1.2`（仅映射） | Release 标记为 Debug/HUD-test；未重新审计 APK 内部版本 | Release 与 Git 标签已从 GitHub 删除；APK 仅保存在本地忽略备份目录，不提供公开下载 |
| `v0.2.16`（已清理） | `v1.1.3`（仅映射） | `versionName=0.2.16-hud-test`，`versionCode=35`，`com.shihab.diplay.hudtest`，Android Debug 签名 | Release 与 Git 标签已从 GitHub 删除；APK 仅保存在本地忽略备份目录，不提供公开下载 |

上表中的新编号只是历史映射，不代表旧 APK 的内部版本，也未改写其提交或二进制；例如不能把 `v0.2.16` 的旧 APK 说成内部版本 `1.1.3`。上述三个 GitHub Release、公开附件和 Git 标签现已清理；原提交仍可从项目分支历史追溯，旧 APK 只保存在本地受忽略的备份目录，旧下载链接不再可用。

GitHub 发布标签、日期、正式/预发布状态、实际附件及可验证的资产摘要，以本页“当前发布状态”同步区和 GitHub Releases API 为准。Android `versionCode` 的不可变分配由 `config/android-version-ledger.json` 管理；本地候选不等于 GitHub 发布。所有用户 APK 必须使用固定 Release 签名、包名 `com.shihab.diplay.hudtest` 与 `CarPaly-XingyueL-v{versionName}.apk` 命名规则。不得交付 Debug APK 或覆盖已交付历史文件。DiPlay 上游版本只用于源码跟踪和移植，不改变 CarPaly 自身版本序列。

## 车型兼容性

“候选配置”表示代码中可以选择或由 Android 构建身份映射得到，不表示吉利官方认证或实车兼容。自动识别仅检查 Android 构建字段中的平台/车型证据，不读取 VIN，也不查询车辆总线。

| 车型/配置 | 代码配置 | 自动化测试 | 实车状态 |
| --- | --- | --- | --- |
| 星越 L 2021 | `KX11_2021` 候选配置和年型映射已实现 | 通用 Geely/KX11 身份规则有单测；该年型映射未单独测试 | **NOT_TESTED** |
| 星越 L 2022 | `KX11_2022` 候选配置和年型映射已实现 | 通用 Geely/KX11 身份规则有单测；该年型映射未单独测试 | **NOT_TESTED** |
| 星越 L 2023 | `KX11_2023` 候选配置和年型映射已实现 | 通用 Geely/KX11 身份规则有单测；该年型映射未单独测试 | **NOT_TESTED** |
| 星越 L 2024 | `KX11_2024` 候选配置和年型映射已实现 | 通用 Geely/KX11 身份规则有单测；该年型映射未单独测试 | **NOT_TESTED** |
| 星越 L 2024 天际版 | 优先候选配置；可从明确的天际版标识映射 | 合成构建身份对天际版识别及标签有单测 | **NOT_TESTED** |
| 星越 L 2025 | `KX11_2025` 候选配置和年型映射已实现 | 通用 Geely/KX11 身份规则有单测；该年型映射未单独测试 | **NOT_TESTED** |
| 星越 L 2026 | `KX11_2026` 候选配置和年型映射已实现 | 通用 Geely/KX11 身份规则有单测；该年型映射未单独测试 | **NOT_TESTED** |
| KX11 Generic | 未知年型的通用候选回退配置已实现 | 通用标签有单测；Generic 回退本身未单独测试 | **NOT_TESTED** |

自动识别规则要求 Geely/ECARX 平台证据与 KX11/Xingyue/Monjaro 车型证据同时匹配。当前测试使用合成输入，不是车机读取结果。

## 功能状态

| 功能 | 当前代码状态 | 自动化验证 | 吉利实车 |
| --- | --- | --- | --- |
| 车型自动识别 | 已实现保守的构建身份识别和候选年型映射 | 合成身份规则有单元测试 | **NOT_TESTED** |
| 手动车型选择 | 已实现候选配置选择与本机持久化 | 未做车机端到端验证 | **NOT_TESTED** |
| Geely CarPlay 车辆按钮 | 默认名称 `GEELY`、吉利图标独立于车型识别；自定义名称/图标优先 | 默认值、旧默认迁移与设置 UI 有单测 | **NOT_TESTED** |
| 视频显示 | 接收端视频解码/显示代码保留；KX11 配置检查实际视口，不伪造屏幕尺寸 | 有软件级单元/组件测试 | **NOT_TESTED** |
| 有线 CarPlay | USB、iAP2/USBMux 等接收路径代码存在 | 有协议/组件测试；认证与设备互通未验证 | **NOT_TESTED** |
| 无线 CarPlay | Wi-Fi/网络发现及连接路径代码存在 | 有网络状态和组件测试 | **NOT_TESTED** |
| CarPlay 实车连接（模式未记录） | 用户反馈 v1.1.4 在一辆星越 L 上连接成功；维护者未独立复测 | 软件测试不验证真实握手 | **USER_REPORTED_PASS（单车反馈，不代表全车型）** |
| 原车音乐音频 | v1.1.4 有单车可播放反馈；近期另有约一秒后自动暂停的用户反馈（测试包版本未记录） | 音频映射、AudioTrack 和 AudioFocus 有软件测试；OEM 混音策略未知 | **USER_REPORTED_ISSUE（待复现）** |
| 导航语音 | Geely 配置默认把导航提示路由到 `STREAM_MUSIC`；保留可调路由和诊断日志 | 默认值及映射有单元测试 | **USER_REPORTED_FAIL：用户反馈无声，待实车回归** |
| 通话音频流 | 新增独立设置；自动模式使用通信用途，手动模式可选 Android 流编号；0 明确代表 `STREAM_VOICE_CALL` | 路由映射、独立持久化、AudioFocus 与麦克风通路有软件测试 | **NOT_TESTED** |
| Siri | Siri 请求和媒体按键转发代码存在；用户近期反馈 Siri 双向语音正常 | 维护者未独立复现，且测试包版本未记录 | **USER_REPORTED_PASS（未独立复现）** |
| 麦克风 | 有可选 CarPlay 麦克风上行代码；诊断页麦克风自检需用户授权 | 本机自检不等于 CarPlay 通话验证 | **NOT_TESTED** |
| 方向盘按键 | Android MediaSession 可转发常见播放/暂停/上一曲/下一曲媒体键；用户近期反馈按键有响应 | 具体按键映射未记录，维护者未独立复现 | **USER_REPORTED_PASS（未独立复现）** |
| 全屏与系统栏 | 有沉浸式显示及系统栏 Insets 安全区回退 | 有视口/Insets 软件测试 | **用户反馈顶部原车状态栏仍遮挡，修复及实车回归待完成** |
| 倒车/360 优先级 | 未实现星越 L 专用倒车或 360 接管接口 | 无 | **NOT_IMPLEMENTED** |
| HUD/仪表 | 有通用 CarPlay cluster/副屏相关代码；无星越 L OEM HUD 接口 | 不代表仪表显示通过 | **NOT_TESTED** |
| 诊断中心 | 已实现只读状态面板，覆盖 USB、Wi-Fi、蓝牙、音频/按键状态 | 诊断模块单元测试已纳入 CI | **NOT_TESTED** |
| 日志查看 | 已实现实时/历史查看、模块筛选和错误筛选 | 日志管理单元测试已纳入 CI | **NOT_TESTED** |
| 日志导出 | 已实现用户发起的脱敏 ZIP 导出、路径和容量管理 | ZIP/脱敏/限额有单元测试 | **NOT_TESTED** |
| APK 安装 | 历史内部 Debug/HUD-test 构建通过 Android v2 签名检查（不是用户交付物） | CI 内部构建与静态签名检查 | **未在目标车机安装验证** |

自动化测试只验证软件行为。此表中的 **NOT_TESTED** 不应被理解为“基本兼容”或“等待认证”。

## 已实现、开发中与未验证

**已实现（软件层面）**

- KX11 年型候选配置、保守的自动识别和手动选择。
- 默认 CarPlay 车辆按钮名称为 `GEELY`，默认图标为吉利标志，与车型检测结果无关；用户自定义名称和图标优先。仅对旧版完整的 DiPlay/DiPlay/BYD 默认三元组执行迁移，无法确认来源的单独 BYD 值按用户数据保留。
- 媒体、导航和通话音频流独立保存；通话自动路由与 Android 真实流编号 `0` 分开处理。是否能通过星越 L 原车扬声器/麦克风仍需实车确认。
- 只读诊断中心；不读取车辆身份信息，不调用 CAN、UDS、Vehicle HAL 或 Geely 私有 Binder 接口。
- 默认关闭、手动开启/停止的日志管理；日志状态持久化。
- 实时与历史日志、模块/错误筛选、路径显示与复制、手动清理。
- 日志轮转及容量/时间上限：单文件 5 MiB、总量 50 MiB、最多 20 个文件、保留 7 天；结构化历史最多 300 条。
- 用户选择保存位置的 ZIP 导出；不会自动上传诊断数据。
- GitHub Actions 自动化测试、Lint、供 CI 内部验证的 Debug 编译和安全扫描（不公开上传 Debug APK）。

**开发中 / 待设备验证**

- 当前候选版本与公开 Release 的状态见本页顶部自动同步区；`versionCode` 分配以 `config/android-version-ledger.json` 为准。
- 2024 天际版优先：有线/无线 CarPlay、音视频和原车音频回归；收到的单车连接/音乐反馈不代替回归结果。
- Siri、麦克风以及具体方向盘按键在目标车机上的映射。
- 诊断状态与实车行为的对照及性能观察。

**未实现或未验证**

- 星越 L 倒车影像/360 环视接管、车型专用 HUD/仪表输出。
- 所有列出年型的实车兼容认证。
- Apple CarPlay 配件认证或由本项目提供认证材料。
- APK 在实际车机上的安装和完整会话验证。

## 诊断中心与日志

从应用设置中打开“吉利车机诊断中心”。诊断面板以只读方式显示接收端和 Android 状态；软件支持情况不代表车机接口已经可用。

1. 日志默认关闭。需要排查问题时，在诊断中心手动开启；复现后手动停止。
2. 可查看实时/历史日志，按模块筛选，或只看错误；也可查看应用内日志路径并复制。
3. 系统按单文件 5 MiB、总量 50 MiB、20 个文件、7 天自动轮转/清理。
4. 用户点击“导出诊断 ZIP”并选择保存位置后才生成导出包；已导出的 ZIP 不会随应用内清理删除。
5. 导出前仍建议用户检查内容，并仅通过自己选择的渠道发送给开发者。

日志不会自动上传。脱敏用于减少本机路径等信息暴露，但不应把任何诊断包视为绝对不含个人信息；分享前请自行审核。

## APK 下载与安装

<!-- CARPALY:DOWNLOADS:START -->
- **最新正式 Release 页面：** [v1.1.56](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.56)；APK 未通过当前验证记录核对，不提供直链。
- **本地候选：** v1.1.57 / versionCode 45，尚无公开下载链接。
- **发布元数据冲突：** GitHub 将 v1.1.52 标为正式 Release，但人工正文仍含预发布措辞；正文保持原样。
- 预发布及历史附件仅在各自 Release 页面标示，不代表当前正式推荐版本。
<!-- CARPALY:DOWNLOADS:END -->
- **暂无覆盖全部车型、连接模式和功能的实车验证正式版本。**已有单车连接/音乐反馈，导航语音和顶部状态栏问题仍待解决。

### 安装要求

- Android 7.1 / API 25 或更高版本；车机还需提供应用所需的 USB Host、Wi-Fi/蓝牙和 Android 音频能力。
- 测试构建可能需要在系统设置中允许从当前文件来源安装应用。
- 按系统提示授予实际连接/音频功能所需权限；麦克风测试仅在用户明确授权后开始。
- Debug APK 使用调试签名，通常不能覆盖安装正式签名版本。Android 只有在包名相同且签名证书兼容时才允许覆盖升级；如果签名不一致，不要先卸载现有应用，以免丢失本地设置和日志。
- v1.1.4 使用正式 Release 签名。安装任何后续版本覆盖升级前，应确认交付包的签名指纹与已安装版相同；升级失败时保留现有安装并反馈错误，不要清除用户数据。

### 首次使用建议

1. 车辆安全停稳后安装 APK 并启动应用。
2. 在设置中先保留“自动”，或手动选择对应 KX11 候选配置。选择配置只改变接收端参数，不会启用车辆控制接口；变更后按界面提示重新连接。
3. 按界面提示尝试 USB 或无线连接。连接模式、车辆配置和实际结果应一并记录；单车反馈不保证其他年款、配置或连接方式。
4. 如需排障，打开诊断中心查看状态；仅在复现问题前手动开启日志，完成后停止。
5. 使用 ZIP 导出并选择保存位置；检查日志后再通过 GitHub Issue 等渠道提交。

## 常见问题

**选了 2024 天际版，是否表示车型已适配？**

不是。它是候选接收端配置；现有自动测试使用合成系统属性输入。用户报告过一辆星越 L 连接 CarPlay 并播放音乐，但没有提供完整配置/连接模式的复测证据，不能据此宣称该年款全系兼容。

**为什么 CarPlay 可能无法连接？**

车机 USB/Wi-Fi 行为、iPhone 配对状态、Android 权限、网络隔离和认证能力都可能影响连接。本仓库不包含 CarPlay 认证私钥；请先用诊断中心检查可见状态，不要尝试未验证的车辆接口。

**原车蓝牙音频、Siri 或方向盘键会工作吗？**

对应的软件路径或通用 Android 媒体键处理代码存在，但吉利车机的音频焦点、实体按键映射和通话路径没有实测。

**倒车影像、360 环视或 HUD 能否显示？**

星越 L 专用接管/HUD 接口目前未实现。原车安全功能优先，不要以本项目替代原车影像或驾驶辅助系统。

**在哪里下载 APK？**

下载入口与附件名称请查看[当前 APK 下载与安装](#apk-下载与安装)中的自动同步区。旧 Release 资产保留原有标题、标签与字节，不为适配新规则而改写；本地候选不会显示为公开下载。

**音乐有声，为什么导航语音仍可能无声？**

CarPlay 会把音乐、导航提示、Siri 和通话作为不同音频类型处理。当前源码保留 Geely 配置将导航默认路由到 `STREAM_MUSIC` 的策略，但最终是否经过车机扬声器仍取决于车机音频策略；用户反馈导航语音无声，仍需可安装的新测试包和实车结果确认。

**日志会自动发给开发者吗？**

不会。日志默认关闭；只有用户手动开启、选择导出并自行分享后，诊断内容才离开本机。

## 开发环境与源码构建

当前工程使用 JDK 25、Gradle Wrapper 9.5、Android SDK Platform 37 和 NDK 28.2.13676358。先安装 Android SDK 并设置 ANDROID_HOME / ANDROID_SDK_ROOT，再执行：

~~~powershell
.\gradlew.bat :mobile:assembleDebug
~~~

Windows 下运行单元测试和静态检查：

~~~powershell
.\gradlew.bat :shared:testDebugUnitTest :common:testDebugUnitTest :home:testDebugUnitTest
.\gradlew.bat :mobile:lintDebug :home:lintDebug :maphost:lintDebug
~~~

Debug APK 输出位置：mobile/build/outputs/apk/debug/mobile-debug.apk。该变体包名带有 HUD-test 后缀。仓库 CI 会运行源码安全检查、单元测试、Lint、APK 签名/包元数据校验，并上传诊断构建产物；CI 通过不等于实车验证通过。

根目录 README.md 和 `config/public-markdown-allowlist.json` 中列明的审阅版项目文档可以公开提交；其余普通 Markdown、个人授权记录、实车测试结果和临时开发日志仍只保存在本地。v1.1.51 七个 APK 的静态接口分析与适配进度见[吉利报告索引](docs/geely/README_ZH.md)。

## 问题反馈

请通过[GitHub Issues](https://github.com/Qwy20040320/carpaly/issues/new/choose)提交问题。建议附上：

- 车机 Android 版本、车型/年款/配置，以及 APK 版本。
- 有线或无线连接方式、复现步骤和预期/实际现象。
- 经本人检查、主动导出的诊断 ZIP（如有）。

请勿上传 VIN、手机号、账号凭据、CarPlay 认证材料、私钥，或未经本人审查的车辆日志。

## 路线图

- [x] KX11 候选配置与保守识别逻辑。
- [x] 只读诊断中心、可控日志、脱敏 ZIP 导出和自动化检查。
- [ ] 由用户在安全停车状态下完成 2024 天际版优先实车测试。
- [ ] 根据用户授权的日志验证有线/无线连接、音视频、原车音频、Siri/麦克风和方向盘按键。
- [ ] 仅在公开接口、许可和安全评估通过后研究车型专用 HUD/倒车相关能力；不发送未验证控制命令。
- [ ] 完成实车验证和发布审查后，再考虑正式 Release。

## 安全与隐私

- 不保证所有 Android 车机或星越 L 年型兼容；车型配置不等于认证。
- 未经验证的车辆接口保持禁用；不发送未知 CAN/UDS 控制命令。
- 不在仓库发布 CarPlay 认证私钥或用户凭据。
- 诊断日志默认关闭，不自动上传；日志 ZIP 仅在用户主动导出和分享后离开设备。
- 日志分享前由用户检查；不要提交 VIN、账户标识或其他个人信息。
- 所有实车测试必须在安全停车状态下进行，不要在行驶中操作应用或诊断功能。

## 许可证与致谢

项目主体按 [GNU GPL-3.0](LICENSE) 发布，并保留原 DiPlay 项目的版权与许可信息。第三方组件和资源可能采用不同条款；请同时查看仓库中的许可证与 NOTICE 文件。BYD HUD 图标资源尤其采用单独的 PolyForm Noncommercial 许可，见 shared/src/main/assets/byd-hud-icons/LICENSE-BYDMate.txt 和 NOTICE.txt；这些资源不因项目主体采用 GPL-3.0 而重新许可。

Geely CarPlay 返回图标采用 [Geely Auto 2023 标志](https://commons.wikimedia.org/wiki/File:Geely_Auto_2023.svg)制作；该文件页将其列为 PD-textlogo，同时提示可能存在商标等其他限制。此标志仅用于标识接收端品牌兼容性，CarPaly 不隶属或获吉利官方认可。

感谢 [DiPlay](https://github.com/shihabal3amri/DiPlay) 原作者和贡献者。CarPaly 与 Apple、吉利、ECARX 及 BYD 均无官方隶属关系。

---

## English

CarPaly is a community Android CarPlay receiver derived from [DiPlay](https://github.com/shihabal3amri/DiPlay), with candidate profiles for Geely Xingyue L / KX11. The 2024 Tianji edition is the first validation target. Profiles and unit tests are not proof of vehicle compatibility: no model year has complete vehicle validation. One user reported a successful CarPlay connection and music playback on a Xingyue L; the setup was not independently reproduced and must not be generalized to other trims or connection modes.

### Current status

- Candidate model-year profiles, conservative build-identity detection, and manual profile selection are implemented.
- The default CarPlay vehicle button uses the `GEELY` label and Geely icon regardless of profile detection; user-selected names/icons take priority. Legacy migration only rewrites the exact known default tuple. This UI has not been validated in a Geely vehicle.
- Media, navigation, and call stream preferences are independent. Call “Auto” uses voice-communication attributes; a manual Android stream value of `0` remains selectable as `STREAM_VOICE_CALL`. Head-unit routing has not been validated in a vehicle.
- USB and Wi-Fi receiver paths, media/audio handling, and generic CarPlay cluster-related code are present; no Geely OEM integration has been independently confirmed.
- A later user report says CarPlay connected and Siri/steering keys responded, while music paused after about one second outside Siri use, navigation prompts were silent, and the OEM top status bar still overlapped the display. The tested APK version and connection mode were not recorded, and these reports have not been independently reproduced. HUD, instrument-cluster guidance, and fuel data remain **NOT_TESTED**.
#### Recent vehicle reports (user-reported, not independently reproduced)

<!-- CARPALY:ENGLISH_VEHICLE_FEEDBACK:START -->
| Feature | Reported status | Evidence note |
| --- | --- | --- |
| CarPlay connection | User reported pass (not independently reproduced) | User reported a normal connection; APK version, vehicle trim, and wired/wireless mode were not recorded and have not been independently reproduced. |
| Media playback | User reported issue | User reported that music pauses after about one second, while playback works when Siri is active. |
| Navigation prompts | User reported fail | User reported silent navigation prompts; the root cause and any fix have not been confirmed by a new vehicle retest. |
| Siri two-way audio | User reported pass (not independently reproduced) | User reported hearing Siri and being heard by Siri; not independently reproduced. |
| Steering-wheel keys | User reported pass (not independently reproduced) | User reported responsive keys; individual keys and mappings were not recorded and have not been independently reproduced. |
| OEM top status bar | User reported fail | User reported that the OEM status bar still overlaps the CarPlay view. |
| HUD, cluster, and fuel data | NOT_TESTED | No verifiable in-vehicle interface call or acceptance evidence is available. |

The tested APK version is not recorded for this report; do not infer full-model or connection-mode compatibility.
<!-- CARPALY:ENGLISH_VEHICLE_FEEDBACK:END -->

- The read-only diagnostic center, opt-in bounded logs, filtering, redaction, and user-triggered ZIP export are implemented and covered by software tests.
- Reverse-camera/360 takeover and Geely-specific HUD integration are not implemented.
- Historical tags `v0.1.0`, `v0.1.1`, and `v0.2.16` are retained only as version-history mappings in this README; their GitHub Releases, public APK assets, and tags have been removed. Their commits remain reachable from project branches, while APK backups remain local and are not download links.
<!-- CARPALY:ENGLISH_RELEASES:START -->
Latest formal Release: [v1.1.56](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.56); no APK link is provided because its asset has not been matched to the current verification record.

The GitHub channel metadata for v1.1.52 conflicts with pre-release wording in its hand-written notes; the notes are preserved.

Local candidate: `v1.1.57` / code `45`; no public tag, Release, or download URL. Its APK metadata and signer are locally checkable, but source reproducibility against the integrated commit is not established. Vehicle behavior remains NOT_TESTED.
<!-- CARPALY:ENGLISH_RELEASES:END -->

### Download and setup

<!-- CARPALY:ENGLISH_DOWNLOADS:START -->
See the [latest formal Release page](https://github.com/Qwy20040320/carpaly/releases/tag/v1.1.56). No direct APK link is provided until the asset is matched to its verification record. Local candidate `v1.1.57` / code `45` is not public.
<!-- CARPALY:ENGLISH_DOWNLOADS:END -->

Do not uninstall an existing install or clear app data to work around signer/version issues. This is not a claim of complete vehicle validation. The project requires Android API 25 or later. For source builds, use JDK 25, Gradle Wrapper 9.5, Android SDK Platform 37, and NDK 28.2.13676358, then run:

~~~powershell
.\gradlew.bat :mobile:assembleDebug
~~~

Logging is off by default and is never uploaded automatically. Exported diagnostics are user-controlled and should be reviewed before sharing. Do not send unknown CAN/UDS commands; test only while safely parked.

### License and support

The project code is GPL-3.0; third-party components/assets may have separate terms. See [LICENSE](LICENSE) and the relevant NOTICE files. Report bugs or request features through [GitHub Issues](https://github.com/Qwy20040320/carpaly/issues/new/choose).

The Geely CarPlay return icon is adapted from [Geely Auto 2023.svg](https://commons.wikimedia.org/wiki/File:Geely_Auto_2023.svg), which its file page lists as PD-textlogo and notes may still have trademark restrictions. It identifies receiver-brand compatibility only; CarPaly is not affiliated with or endorsed by Geely.
