# Fake Ultra APK 静态分析

## 样本与方法

- 样本：`GeelyCarPlay_Fake Ultra_by_stonezzz.apk`，来源为本机 Downloads。
- 包名 / 版本：`io.dushu.car` / `0.3.2-protected-test`，versionCode 23；minSdk 28，targetSdk 37。
- 大小 / SHA-256：9,506,416 bytes / `5b0b367d34650b029997e461b4de2fb6c1e9407636faf19bbb7a4e15a83019fd`。
- APK v2 签名校验通过；签名者 SHA-256：`30cee9f4a526522845e6ce777a2e214c3bafa006aab99fd7cadca2a37885752d`。这只标识样本，不证明吉利/ECARX 背书或调用授权。
- 使用 Android SDK 工具及官方 JADX 1.5.6 对副本离线检查。JADX 完成 3,718 个处理项，但以 88 个解码错误退出；报告仅陈述能够交叉确认的部分。未运行 APK、JNI 库或注入载荷。
- 私有反编译输出留在仓库外的本机分析目录；不提交 APK 或反编译源代码。

## Manifest、组件与 native 代码

Manifest 可见普通 USB、Wi-Fi、蓝牙、位置、录音、前台服务权限，以及悬浮窗权限；本次检查未见 `geely.oneos.permission`、ECARX/DIM 权限或车辆写权限。可见 `GeelySelfDrawSettingsActivity`、`GeelyClusterSettingsActivity` 及 CarPlay 主机组件。权限声明不等于获授。

仅发现 `libandroidx.graphics.path.so`、`libxcertplay_i2c.so`、`libxcertplay_opus.so`（按 ABI 不完全相同）。未发现能够确认 OneOS、ECARX、DIM 或车辆数据服务绑定的 JNI 符号/调用路径。

## 第二显示器调用路径

- `defpackage.v3.m(Context, int): tb0` 通过 Android `DisplayManager` 枚举屏幕，要求 OEM 标识包含 `ecarx`/`geely` 或存在 `com.ecarx.*`/`com.geely.*` 系统包；排除默认显示，并筛选 1920×1080 的目标 display id。
- `defpackage.v3.n(Context)` 从 `geely_cluster_safe_area` 偏好读取 `display_id`，默认值为 2。默认 id 不是对实际 HDMI2 的硬件映射证明。
- `defpackage.lb0` 注册 `DisplayListener`，创建 `defpackage.xa0` 的 Display/Surface 显示路径，回报 surface 可用/消失；CarPlay 主机将 `Surface` 交给内部视频处理入口 `u7.b(111, surface)`。样本日志称其“HDMI2 presentation”，但静态证据只能确认 Android 第二显示器 Surface 路径，不能确认该显示器就是某车型的 HDMI2、原厂 DIM 或合法 HUD sink。
- `GeelyClusterSettingsActivity` 中存在 1920×720 的安全区域/画布配置。不同页面里画布与显示筛选尺寸不一致，不能据此推出实际车辆面板规格。
- `lb0` 周围还出现 `qb0.c(3)` / `qb0.c(1)` 的工厂地图模式副作用。语义和车辆风险不可确认，因此不复制、不调用。

## 仪表选项与数据来源

`GeelySelfDrawSettingsActivity.p()` 保存 `self_draw_*` 布尔偏好，包括车速、转速、平均油耗、左右仪表、封面和动态仪表等。当前可读 DEX 中未找到这些值完整连至真实车辆数据 provider 和绘制数据的闭合路径；不能据 UI 选项宣称其数值有效或来源于车辆。CarPlay Host 可把第二屏 Surface 接到视频链路并转发 artwork 回调，证明有样本内部 app-drawn 路径线索，不证明真实车速/RPM读取、OEM仪表控制或安全显示优先级。

## 结论

| 项目 | 证据状态 | 是否可直接移植 |
|---|---|---|
| Android DisplayManager 枚举 / 第二屏 Surface | `CALL_SITE_CONFIRMED` | 可复用公开 Android 模式，但需自己的设备检查和生命周期测试 |
| OneOS / ECARX / DIM 服务 | 未发现可确认调用点 | 否 |
| 原厂 HDMI2 / HUD / 仪表授权 | 未确认 | 否 |
| 动态车辆数据 provider | 未确认 | 否 |
| 实车第二屏输出 | `NOT_TESTED` | 不得声称已验证 |

失败回退应保持 CarPlay 主屏不变、第二屏隐藏/结束，不写任何车辆数据。样本静态线索不构成对样本作者或 OEM 的授权。
