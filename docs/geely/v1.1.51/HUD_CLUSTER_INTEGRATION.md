# CarPaly v1.1.51 — HUD、仪表与歌词接口评估

## 星越 L 车控 2.2：HUD Native 线索

样本包 `com.xingyue.gmcustom` 的 Manifest 导出 `com.xingyue.gmcustom.hud.MapSurfaceProviderService`，并出现 `IMapSurfaceProvider`、`NAVI_ROUTE_READY`。这是该 APK 声明的应用组件，不等于吉利系统公开 SDK。没有还原出可供 CarPaly 稳定 bind 的 AIDL 定义、接口描述符、回调数据结构、调用权限或服务端访问控制。

`assets/libgmhud.so` 是 arm64 ELF/SONAME `libgmhud.so`。Native 动态符号含：

- `HudIpcClient::ensureServiceConnected(JNIEnv*)`
- `HudIpcClient::queryMapSurface(JNIEnv*, long, HudSurfaceResult&)`
- `HudIpcClient::getCachedSurface(JNIEnv*)`
- `HudIpcClient::reportRuntimeStatus(JNIEnv*, int, const char*)`
- `HudRenderHook::mountAndRender(JNIEnv*, jobject, int, int)`、`syncRoute(JNIEnv*)`、`syncCarPosition(JNIEnv*)`、`directDrawRouteToSub(JNIEnv*, jobject, jobject)`、`extractActivePathId(JNIEnv*, jobject, int*)`、`applyOptimalZoomAndLock(JNIEnv*)`、`stopRender(JNIEnv*)`
- `HudVisualGate` 的地图样式、路径过滤和 HUD bubble/layer 抑制函数。

`llvm-strings` 还找到对 `com.geely.hud.HudExtScreenManager`、`MultiScreenInfo`、`AidlWidgetExtScreen.startNavi/stopNavi/startRender/stopRender` 的 JNI 方法查找字符串，以及 `com.geely.map`、`NAVI_ROUTE_READY`。这些是库对目标 Java 类/应用私有层的操作意图。可读 DEX 未找到闭合的 `System.loadLibrary("gmhud")` -> Java 调用 -> SDK/系统服务路径；符号也不是稳定公开的 Android Java API。没有发现可确认的 HUD 歌词方法。

`assets/gm_inject`（21,448 字节）属于样本包中的不透明资产，本轮不执行、不移植、不在 CarPaly 进程中加载。若它负责把 Native hook 注入其他进程，必须先取得正式、可审计的厂商集成协议；当前无此证据。

## 嵌套 Dushu 插件与歌词

`assets/plugins/dushucar.apk` 是另一个 APK（`io.dushu.car`，2.2 / code 8，min 24 / target 33）。其独立签名为 Android Debug 证书，Manifest 主要包含启动/媒体相关组件。JADX 可读逻辑包括 `MediaListenerService`、`MediaControlReceiver`、`ActiveMediaResolver`，通过 Android MediaSession/媒体键定位和控制播放对象；未发现 CarPlay 导航或 HUD Surface 写入链路。

星舱 DEX 有 `DashboardMediaLyric(text, source, updatedAtElapsedMs, staleAfterMs)` 模型和歌词/媒体快照数据流。它证明样本应用存在 dashboard lyric 数据表达，不证明数据送至 `libgmhud.so`、`MapSurfaceProviderService` 或某个原车 HUD。歌词对车机的输出接口、时间同步、导航语音优先、断线清理与倒车/360 优先级均未确认。

## 星舱助手：DIM / 仪表导航

静态代码可追踪 `DimInteraction.create(context)`、`getDimMenuInteraction()`，以及反射查找 `getNaviInteraction()`、单参数 `registerNavigationInteractionCallback(...)`、`notifyTurnByTurnStarted()` 与 `setPresentationToDimSwitch(boolean)`。`DIMProtocolManager.getNaviMode()` 是可见的模式读取入口。反射只约束方法名或 arity；被反射 callback 的参数类型、转向/距离/道路/车道字段、服务生命周期、数据写入边界没有完整恢复。

因此现有材料只能说明样本应用具有一条 DIM 激活/回调探索路径，不能判断导航事件读写是否分离、是否是 OEM 授权系统应用、是否适用于 2024 天际版。CarPaly 当前通用 cluster/map 组件与这条 DIM API 无关。

## 倒车、360 与显示优先级

五份 APK 未提供可供 CarPaly 复用的稳定倒车/360 优先级契约。任何“暂停 HUD”“隐藏安全图层”类 Native hook 会改变原车展示行为，当前不能接入。CarPaly 应保持 fail-closed：不在未知倒车/360/车机安全界面上覆盖自绘内容，也不发送未验证的导航停止/恢复命令。

## CarPaly 当前实现与测试边界

`BydNavigationOutputs`、`BydHudBridge`、`BydClusterBridge` 是 BYD 路径，不是 Geely adapter；`BydOutputSettings.vehicleOutputsAllowed()` 要求 BYD 设备识别并显式打开。GEELY Profile 不经过 BYD writer gate 的回归测试通过后，也仅说明不会误写 BYD 目标。没有 Geely HUD、HUD 歌词或 DIM 输出代码。

| 检查项 | 状态 | 证据边界 |
|---|---|---|
| 星越 L HUD 导航 | `BLOCKED` | Native 内部 Hook 符号，不是已授权 SDK |
| 地图 Surface 获取 | `BLOCKED` | exported app service 有名字，无可审计外部 Binder 契约 |
| HUD 歌词 | `UNKNOWN` | 有 dashboard lyric model，无 HUD writer |
| DIM / 仪表导航 | `PARTIAL`（仅接口探索线索） | 反射方法名/局部 arity；无 packet schema/权限 |
| 倒车/360 显示优先级 | `UNKNOWN` | 无确认调用契约；不得打断车机安全 UI |
| 2024 天际版运行验证 | `NOT_TESTED` | 本次没有连接实车 |

解锁所需证据：吉利/ECARX 正式 SDK 或书面集成规范、可验证的 service/AIDL 版本、目标固件调用权限和系统允许的安装身份，再在驻车实车上仅做只读探测，获得授权后才逐步验证显示输出。不得从现有样本中复制 Native 注入/Hook 实现。

## Fake Ultra 新样本核对

新样本 `io.dushu.car` 的 `DisplayManager`/第二屏 Surface 静态调用点已补充到 `GEELY_HDMI2_DISPLAY_ANALYSIS.md`。`HDMI2` 日志文字与默认 `display_id=2` 不构成物理 HDMI、原厂仪表或 HUD 映射证据；样本未发现可确认 DIM/HUD OEM service、permission 或写入契约。车速/RPM/油量等开关目前没有闭合到可信车辆 provider 的静态路径。CarPaly 不新增 Geely 输出器，不把 app-drawn 第二屏描述为仪表接管。
