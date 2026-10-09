# CarPaly

### Geely Xingyue L / KX11 CarPlay Receiver

[![Android CI](https://github.com/Qwy20040320/carpaly/actions/workflows/android.yml/badge.svg?branch=main)](https://github.com/Qwy20040320/carpaly/actions/workflows/android.yml)
[![GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
![Android](https://img.shields.io/badge/Android-API%2025%2B-green)

> 中文为主 · English summary below。CarPaly 是社区开发中的 Android CarPlay 接收端项目，不是吉利、ECARX、Apple 或任何车机厂商的官方软件。

## 项目简介

CarPaly 基于开源项目 DiPlay 持续开发，重点为吉利星越 L（内部代号 KX11）提供一个可审慎选择的接收端配置，并完善只读诊断、可控日志和开发者构建流程。2024 天际版是当前优先验证目标。

车型配置、协议代码或自动化测试通过，都不等于某一款车已经兼容。当前没有经过实车验证的车型；有线/无线 CarPlay、音频、麦克风、Siri 和方向盘按键均不得视为已在星越 L 上验证。

## 项目定位与目标

- 在 Android 车机上运行 CarPlay 接收端；保留 DiPlay 已有的 USB、网络、音视频接收代码。
- 根据明确的 Geely/ECARX 与 KX11 身份证据选择接收端配置；分辨率本身不会被当作车型证据。
- 优先验证星越 L 2024 天际版，同时保留 2021–2026 年型和 KX11 Generic 候选配置。
- 通过诊断中心帮助用户安全采集本机连接状态；不访问未经授权的车辆总线或私有车机服务。
- 只在取得公开、可验证的接口依据并完成安全评估后，考虑扩展车机集成。

本项目不提供 Apple 配件认证，不包含 CarPlay 认证私钥，也不保证未经测试的车机可以建立 CarPlay 会话。

## 与 DiPlay 的关系

CarPaly 是 [shihabal3amri/DiPlay](https://github.com/shihabal3amri/DiPlay) 的社区派生项目，保留原项目要求的 GPL-3.0 许可与版权声明，并在此基础上开发 KX11 候选适配、诊断和日志功能。原项目远程仍作为开发参考；详见下方许可证与致谢。

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
| 视频显示 | 接收端视频解码/显示代码保留；KX11 配置检查实际视口，不伪造屏幕尺寸 | 有软件级单元/组件测试 | **NOT_TESTED** |
| 有线 CarPlay | USB、iAP2/USBMux 等接收路径代码存在 | 有协议/组件测试；认证与设备互通未验证 | **NOT_TESTED** |
| 无线 CarPlay | Wi-Fi/网络发现及连接路径代码存在 | 有网络状态和组件测试 | **NOT_TESTED** |
| 原车音频 | 有 Android 音频路由选项，也有让手机继续使用车载蓝牙音频的选项 | 软件路径有测试；吉利混音策略未知 | **NOT_TESTED** |
| Siri | Siri 请求和媒体按键转发代码存在 | 无星越 L 端到端 Siri 测试 | **NOT_TESTED** |
| 麦克风 | 有可选 CarPlay 麦克风上行代码；诊断页麦克风自检需用户授权 | 本机自检不等于 CarPlay 通话验证 | **NOT_TESTED** |
| 方向盘按键 | Android MediaSession 可转发常见播放/暂停/上一曲/下一曲媒体键 | 车机实体按键映射未验证 | **NOT_TESTED** |
| 倒车/360 优先级 | 未实现星越 L 专用倒车或 360 接管接口 | 无 | **NOT_IMPLEMENTED** |
| HUD/仪表 | 有通用 CarPlay cluster/副屏相关代码；无星越 L OEM HUD 接口 | 不代表仪表显示通过 | **NOT_TESTED** |
| 诊断中心 | 已实现只读状态面板，覆盖 USB、Wi-Fi、蓝牙、音频/按键状态 | 诊断模块单元测试已纳入 CI | **NOT_TESTED** |
| 日志查看 | 已实现实时/历史查看、模块筛选和错误筛选 | 日志管理单元测试已纳入 CI | **NOT_TESTED** |
| 日志导出 | 已实现用户发起的脱敏 ZIP 导出、路径和容量管理 | ZIP/脱敏/限额有单元测试 | **NOT_TESTED** |
| APK 安装 | 已生成 Debug/HUD-test APK，Android v2 签名校验通过 | CI 会构建并校验 APK | **未在车机安装** |

自动化测试只验证软件行为。此表中的 **NOT_TESTED** 不应被理解为“基本兼容”或“等待认证”。

## 已实现、开发中与未验证

**已实现（软件层面）**

- KX11 年型候选配置、保守的自动识别和手动选择。
- 只读诊断中心；不读取车辆身份信息，不调用 CAN、UDS、Vehicle HAL 或 Geely 私有 Binder 接口。
- 默认关闭、手动开启/停止的日志管理；日志状态持久化。
- 实时与历史日志、模块/错误筛选、路径显示与复制、手动清理。
- 日志轮转及容量/时间上限：单文件 5 MiB、总量 50 MiB、最多 20 个文件、保留 7 天；结构化历史最多 300 条。
- 用户选择保存位置的 ZIP 导出；不会自动上传诊断数据。
- GitHub Actions 自动化测试、Lint、Debug APK 构建和安全扫描。

**开发中 / 待设备验证**

- 2024 天际版优先：USB/无线连接、音视频和原车音频实测。
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

- **GitHub Releases：**[打开发布页](https://github.com/Qwy20040320/carpaly/releases)
- 当前仓库没有已发布的正式 APK Release。CI 生成的是开发/诊断构建产物，不是稳定下载渠道，也不代表车型实测结果。
- **暂无经过实车验证的正式版本。**

### 安装要求

- Android 7.1 / API 25 或更高版本；车机还需提供应用所需的 USB Host、Wi-Fi/蓝牙和 Android 音频能力。
- 测试构建可能需要在系统设置中允许从当前文件来源安装应用。
- 按系统提示授予实际连接/音频功能所需权限；麦克风测试仅在用户明确授权后开始。
- Debug APK 使用调试签名，仅供开发和诊断；不代表 Apple 配件认证或正式发布签名。

### 首次使用建议

1. 车辆安全停稳后安装 APK 并启动应用。
2. 在设置中先保留“自动”，或手动选择对应 KX11 候选配置。选择配置只改变接收端参数，不会启用车辆控制接口；变更后按界面提示重新连接。
3. 按界面提示尝试 USB 或无线连接。当前没有星越 L 实车验证，不能保证配对、认证或连接成功。
4. 如需排障，打开诊断中心查看状态；仅在复现问题前手动开启日志，完成后停止。
5. 使用 ZIP 导出并选择保存位置；检查日志后再通过 GitHub Issue 等渠道提交。

## 常见问题

**选了 2024 天际版，是否表示车型已适配？**

不是。它是候选接收端配置；现有测试是合成系统属性输入。需要用户在真实车辆上验证，状态目前仍为 NOT_TESTED。

**为什么 CarPlay 可能无法连接？**

车机 USB/Wi-Fi 行为、iPhone 配对状态、Android 权限、网络隔离和认证能力都可能影响连接。本仓库不包含 CarPlay 认证私钥；请先用诊断中心检查可见状态，不要尝试未验证的车辆接口。

**原车蓝牙音频、Siri 或方向盘键会工作吗？**

对应的软件路径或通用 Android 媒体键处理代码存在，但吉利车机的音频焦点、实体按键映射和通话路径没有实测。

**倒车影像、360 环视或 HUD 能否显示？**

星越 L 专用接管/HUD 接口目前未实现。原车安全功能优先，不要以本项目替代原车影像或驾驶辅助系统。

**在哪里下载正式 APK？**

请查看 [GitHub Releases](https://github.com/Qwy20040320/carpaly/releases)。目前没有经过实车验证的正式 Release；Actions 产物仅用于开发测试。

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

除根目录 README.md 外，普通 Markdown 开发文档和报告只保存在本地，不会提交到 GitHub。

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

感谢 [DiPlay](https://github.com/shihabal3amri/DiPlay) 原作者和贡献者。CarPaly 与 Apple、吉利、ECARX 及 BYD 均无官方隶属关系。

---

## English

CarPaly is a community Android CarPlay receiver derived from [DiPlay](https://github.com/shihabal3amri/DiPlay), with candidate profiles for Geely Xingyue L / KX11. The 2024 Tianji edition is the first validation target. Profiles and unit tests are not proof of vehicle compatibility: every listed model and every in-car feature remains **NOT_TESTED** until verified by a user in the real vehicle.

### Current status

- Candidate model-year profiles, conservative build-identity detection, and manual profile selection are implemented.
- USB and Wi-Fi receiver paths, media/audio handling, and generic CarPlay cluster-related code are present, but no Geely in-car integration is confirmed.
- The read-only diagnostic center, opt-in bounded logs, filtering, redaction, and user-triggered ZIP export are implemented and covered by software tests.
- Reverse-camera/360 takeover and Geely-specific HUD integration are not implemented.
- A debug/HUD-test APK can be built and signature-checked; it has not been installed or validated in a Geely vehicle.

### Download and setup

See [GitHub Releases](https://github.com/Qwy20040320/carpaly/releases). There is no verified production release yet: **暂无经过实车验证的正式版本。** The project requires Android API 25 or later. For source builds, use JDK 25, Gradle Wrapper 9.5, Android SDK Platform 37, and NDK 28.2.13676358, then run:

~~~powershell
.\gradlew.bat :mobile:assembleDebug
~~~

Logging is off by default and is never uploaded automatically. Exported diagnostics are user-controlled and should be reviewed before sharing. Do not send unknown CAN/UDS commands; test only while safely parked.

### License and support

The project code is GPL-3.0; third-party components/assets may have separate terms. See [LICENSE](LICENSE) and the relevant NOTICE files. Report bugs or request features through [GitHub Issues](https://github.com/Qwy20040320/carpaly/issues/new/choose).
