# CarPaly v1.1.51 — 五个星越 L APK 静态接口提取

## 范围与证据规则

本次只对用户提供且位于本机的 APK 做离线静态检查；没有安装、启动或执行样本中的应用、Native 库、动态载荷或 `gm_inject`。原 APK 和 JADX 输出保存在仓库外的本机分析目录，没有复制进 Git。工具包括 Android SDK `apkanalyzer` / `apksigner`、JADX 1.5.6、NDK `llvm-readelf` / `llvm-nm` / `llvm-strings`。JADX 官方版本记录：[v1.5.6](https://github.com/skylot/jadx/releases/tag/v1.5.6)。

证据级别：`STRING_ONLY` 只证明名称或字符串存在；`SIGNATURE_CONFIRMED` 表示 APK DEX/Native 符号表中可确认类型/签名；`CALL_SITE_CONFIRMED` 表示反编译调用点也可追踪；`RUNTIME_VERIFIED` 仅用于实机/运行时观测。本轮没有 `RUNTIME_VERIFIED` 结果。Manifest 申请某权限不等于系统已授予，也不等于第三方应用有权调用 OEM 服务。

## APK 清单

| 样本 | 包名 / 版本名 (code) | 文件大小 | SHA-256 | 签名者 SHA-256 | 平台及静态结果 |
|---|---|---:|---|---|---|
| `0914.apk` | `com.hyphp.playkeytool` / `26091401` (26091401) | 6,517,326 B | `cd5a09e0917cbbaf497b69f989cc8ecc215352a8ee8d39f66d2a049911dd6463` | `249ebaf6483fd72d7169634bbd594a6ed063c423348f587be46e26aa9b6a3fda` | min 19 / target 29；armeabi-v7a；签名验证通过；BaiduProtect 载荷阻碍应用逻辑还原 |
| `星越L车控2.2-release.apk` | `com.xingyue.gmcustom` / `2.2` (39) | 10,554,078 B | `e3fd3da0f98efb13be72f771451028802f8f48d3b1c8ba67d449a4e502bb69f7` | `9a42d01d70661870a71436807824d8817d92cc0b946e23068e3b56e9f0e98a48` | min 30 / target 36；arm64-v8a；签名验证通过；少量应用类可读，包含 `libgmhud.so` 和嵌套 APK |
| `【必装】星舱助手-v1.2.0.apk` | `tuox.mconfig` / `1.2.0` (6) | 3,731,399 B | `06b168b3919c028f3b976b3f214bf313ea69a269efd97ab0320bd8fa2966a685` | `b0274dc6c5a7a37633dd19f587611dc8db51b4bdf5dbae05bc10509f939aeae8` | min 28 / target 35；arm64-v8a；签名验证通过；部分业务类与嵌入式 OneOS Binder 声明可读，JADX 有 12 个反编译错误 |
| `【必装】星越L车控1.1-release.apk` | `com.xingyue.gmcustom` / `1.1` (2) | 6,639,226 B | `838dd382a7b6a9a3d9239757f332a76009b22b414dfe87bcf9df5bc740f098b1` | `9a42d01d70661870a71436807824d8817d92cc0b946e23068e3b56e9f0e98a48` | min 30 / target 36；有加固库与 loader；没有恢复出可用车辆 API 调用链 |
| `【选装】24-25款马大师车机助手.apk` | `cn.navitool.a2` / `0.5.1` (1) | 5,129,688 B | `5be2f95823fffbbeb06440b07c85d11b2e9f34f2a7df2942ecebebc0a7b7cb4b` | `9193f31fc8d5e632f5444cf4f67af3ce4af54c310d7833818869d7f158a026d8` | min 30 / target 34；加固 stub/native loader；没有恢复出可用车辆 API 调用链 |

上述 APK 的 v2/v3 签名校验均通过各自可用的 Android 签名检查；签名者彼此不同（星越 L 车控 1.1 与 2.2 相同）。这些签名只用于样本身份区分，不表示厂商背书或调用授权。完整包哈希便于在后续提供新版样本时识别是否为同一文件。

## 可恢复接口与调用链

### 星舱助手：OneOS 方向盘输入

- `com.geely.lib.oneosapi.IServiceManager` DEX Binder 描述符为 `com.geely.lib.oneosapi.IServiceManager`；声明 `getService(int): IBinder`（transaction 2）及 `addService(int, IBinder): void`（transaction 1）。
- `com.geely.lib.oneosapi.input.IInputManager` 描述符为 `com.geely.lib.oneosapi.input.IInputManager`；声明 `registerListener(IInputListener, String, int[]): void`（transaction 3）、`unregisterListener(IInputListener, String): void`（transaction 4）及 `getControlIndex(): int`（transaction 5）。
- `IInputListener` 的 Binder 回调声明包含 `onKeyEvent(int,int,int)`、`onShortClick(int,int)`、`onHoldingPressStarted(int,int)`、`onHoldingPressStopped(int,int)`、`onLongPressTriggered(int,int)`、`onDoubleClick(int,int)`；transaction 编号在其 Stub 中可读。参数具体含义、键码枚举和值语义未确认。
- 调用点 `w1/Q0` 显示应用显式绑定 `com.geely.service.oneosapi/.OneOSApiService`，调用 `getService(8)`，转为 `IInputManager` 后以应用包名和过滤数组 `{200400}` 注册 listener；停止时由 `w1/N0` 解除注册并 unbind。`w1/O0` 接收 OneOS 回调并转发至应用内部按键事件处理。代码有异常捕获及有限重试，但这只描述样本行为。
- 这组方法签名和调用点静态确认；OneOS 服务在 2024 天际版是否存在、service id 8 是否跨固件稳定、权限能否由普通安装包取得均未验证。星舱 Manifest 请求 `geely.oneos.permission.SERVICE`、`WRITE_SECURE_SETTINGS` 等权限，不能据此推导 CarPaly 可获授。

### 星舱助手：ECARX 传感器

- `w1/RunnableC0228p0` 调用 `Car.create(context).getSensorManager()`，按符号常量逐个订阅 `ISensor.registerListener(listener, id)`，失败时尝试三参数重载，并在退出时 `unregisterListener(listener)`；循环中读取 `getSensorEvent(int)`、`getSensorLatestValue(int)`、`isSensorSupported(int)`。
- `w1/C0224n0` 的回调签名可从其 `ISensorListener` 实现和调用点确认：`onSensorEventChanged(int,int)`、`onSensorValueChanged(int,float)`、`onSensorSupportChanged(int,FunctionStatus)`。燃油回调将值除以 1000 后格式化；速度回调将值乘以 3.6；RPM 有非有限值过滤。该转换仅是此样本 UI 处理方式，不是厂商单位规范。
- ECARX `ISensor` / `ISensorEvent` API 类型定义及传感器常量数值没有在当前可恢复 DEX 源中出现；部分读取失败路径把值回落为 `0.0`，不应复制为 CarPaly 展示逻辑。`1055232` 是一个未能从样本恢复命名的额外传感器 ID，不能推断其含义。
- ECARX Sensor API 的签名和权限、燃油量值域与单位、2024 天际版实际支持列表均未核实。没有实现 CarPaly 传感器读取。

### 星舱助手：仪表/DIM

可追踪到 `MConfigInitService` 初始化 `DimInteraction.create(context).getDimMenuInteraction()`；另一调用路径用反射查找 `getNaviInteraction()`、一个参数的 `registerNavigationInteractionCallback(...)`、无参数的 `notifyTurnByTurnStarted()`，并尝试 `setPresentationToDimSwitch(true/false)`。`DIMProtocolManager.getInstance(context).getNaviMode()` 读取模式的名称/调用可见。反射路径只匹配方法名和参数个数，callback 参数类、事件字段、路线数据写入契约及权限均未从本 APK 确定。它不是可直接移植的公开 DIM API。

### 星越 L 车控 2.2：HUD 与原车应用服务

- Manifest 声明 `com.xingyue.gmcustom.hud.MapSurfaceProviderService` 为 exported service；可见 intent action / 字符串有 `IMapSurfaceProvider`、`NAVI_ROUTE_READY`。导出组件的存在不等于系统级授权或稳定第三方 Binder 协议。当前可见 Java/Dex 中没有建立其完整服务端接口与客户端鉴权的可复用调用链。
- `assets/libgmhud.so` 为 arm64 ELF；动态符号里有 `HudIpcClient::ensureServiceConnected/queryMapSurface/getCachedSurface/reportRuntimeStatus`、`HudRenderHook::mountAndRender/syncRoute/syncCarPosition/directDrawRouteToSub/extractActivePathId/applyOptimalZoomAndLock/stopRender` 等带 `JNIEnv*` 的 Native 符号。字符串还提到 `HudExtScreenManager`、`AidlWidgetExtScreen.startNavi/stopNavi/startRender`。这是应用内部 Hook/渲染实现的线索，不是厂商公开 SDK；Java 侧加载/授权/设备条件在可读 DEX 中没有闭合。
- `assets/gm_inject`（21,448 B）未执行，也未导入 CarPaly。当前无法从安全可移植角度确认它的加载时机、目标进程、校验或影响，因此不对其功能作断言。
- 嵌套 `assets/plugins/dushucar.apk` 的包名 `io.dushu.car`、versionName `2.2`、code 8、min 24 / target 33；其签名证书为 Android Debug 证书（SHA-256 `0616e28d3d9e839470172144856505bc154716cead858c772573119ea47e1d48`）。可读类包括 `MediaListenerService`、`MediaControlReceiver`、`ActiveMediaResolver`，权限集中于开机接收；代码围绕 Android MediaSession / 媒体键，不构成 HUD API，也没有发现歌词写入 HUD 的调用链。

## 未能恢复及安全边界

`0914.apk` 的 BaiduProtect dex/jar 解包错误阻断了主业务类分析。`HYCarplaySWC` 只在 `android/support/v4/media/session/e.java` 的 AndroidX MediaSessionCompat 兼容类中发现为字段字符串，没有 CarPlay 应用类调用点，故不把它标作 ECARX 按键 API。其 Manifest 虽请求 `com.ecarx.permission.CAR_CONTROL`、`com.ecarx.permission.ADAPT_API` 和 `android.car.permission.CAR_VENDOR_EXTENSION`，但没有权限授予/系统签名证据。

车控 1.1 与马大师样本以加固 loader/native stub 为主；当前没有可审计的传感器、方向盘、HUD、DIM、音频方法签名及调用链，统一为 `UNKNOWN`。本轮没有破解加固、复用私钥、执行 Hook/注入、发送 Binder/车控命令或将任何第三方库放入 CarPaly。

## 小结

五个样本均在本地找到且哈希/签名/Manifest 已检查；部分静态调用点可恢复，保护/加固边界也已保留。没有任何 Geely 车辆接口达到 `RUNTIME_VERIFIED`，也没有证据证明 2024 天际版对普通第三方 APK 开放这些能力。无需为这轮分析重新下载 APK 或重复 JADX 全量输出。
