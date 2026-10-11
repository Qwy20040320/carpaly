# Glauncher APK 静态分析

## 样本与方法

- 样本：`Glauncher_20260629.apk`，本机 Downloads。
- 包名 / 版本：`com.maxinf.car` / `1.0`，versionCode 1；minSdk 24，targetSdk 33；1,604,347 bytes。
- SHA-256：`bbbbb4fdcdc784a53c88cf7605a8a3c35be442068ee06d1e3db583541c337dcd`。
- APK v2 签名校验通过；签名者 SHA-256 为 `30cee9f4a526522845e6ce777a2e214c3bafa006aab99fd7cadca2a37885752d`，与 Fake Ultra 样本相同；不表示 OEM 授权或开发者身份。
- 使用 JADX 1.5.6 离线检查；仅 6 个反编译错误。样本及反编译输出不进入仓库，未执行样本。

## Manifest 与代码

Manifest 中可见 `QUERY_ALL_PACKAGES` 与应用自定义的动态 receiver 权限；没有发现 CarPlay、OneOS、ECARX、DIM、传感器或车辆服务权限，也没有 Native library。

DEX 主要只有 `MainActivity` 与 `PackageReceiver`：Activity 构建通用应用启动器 UI，能够根据注册包列表启动应用，并处理常规沉浸式显示/系统栏状态；布局边距读取 Android 状态栏 dimension。Receiver 处理包添加、删除和替换广播。没有可确认的 CarPlay 会话、iAP2/NCM/AirPlay、媒体音频、MediaSession、OEM service、方向盘、HUD、仪表或燃油代码路径。

## 结论

此 APK 是应用启动器样本，不是 CarPlay 接收器或星越 L 车辆适配 SDK。Android `WindowInsets` 与系统栏行为可作为通用 Android UI 研究线索，但不能当作 CarPlay 视频安全区或 OEM 接口证据。状态为 `STATIC_REVIEWED`; 任何车机/车辆功能均为 `NOT_TESTED`。
