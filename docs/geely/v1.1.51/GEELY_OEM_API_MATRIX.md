# CarPaly v1.1.51 — GEELY OEM 接口适配矩阵

本矩阵把样本中能看到的 API 声明、样本自身的调用点和 CarPaly 代码分开记录。`RUNTIME_VERIFIED` 需要真实车机/运行证据；当前全表没有达到该等级。对于 Android Manifest 的权限声明，只能写“样本申请”，不能写成系统授予。

证据级别：`STRING_ONLY`、`SIGNATURE_CONFIRMED`、`CALL_SITE_CONFIRMED`、`RUNTIME_VERIFIED`。功能状态：`IMPLEMENTED`、`PARTIAL`、`BLOCKED`、`UNKNOWN`、`NOT_SUPPORTED`、`VEHICLE_VERIFIED`。

| 能力 | APK / 内部路径 | API / 方法 | 签名/调用证据 | 权限、车型及第三方条件 | CarPaly 当前对应 | 状态 / 自动测试 / 实车 | 风险与回退 |
|---|---|---|---|---|---|---|---|
| KX11 Profile 识别 | CarPaly `common/.../GeelyVehicleAdapter.kt` | Android `Build` 字段 + 手选 Profile | 自有源码调用；不依赖 OEM SDK | 当前候选 2021–2026、2024 天际版、Generic；Build 字段不构成车辆认证 | `GeelyVehicleAdapter`、`HeadUnitProfile` | `IMPLEMENTED`；`HeadUnitProfileTest` PASS；车型/固件实车 `NOT_TESTED` | 无 OEM 服务时仍只做保守 Profile 选择；无法确认时回落通用 |
| OneOS 方向盘输入 | 星舱 `w1/Q0`、`w1/O0`、`com/geely/lib/oneosapi/input/IInputManager` | `registerListener(IInputListener,String,int[])`；IInputListener 的 click/hold/long 回调 | `SIGNATURE_CONFIRMED` + `CALL_SITE_CONFIRMED`；服务 ID 8、过滤值 200400 | 样本申请 `geely.oneos.permission.SERVICE`；系统服务授予/固件适用/第三方可调用未证实；2024 天际版 `UNKNOWN` | `WheelKeyService` 只消费 Android key 事件；Geely 禁用历史 BYD 默认映射，保留用户学习键 | `PARTIAL`；现有映射/生命周期测试 PASS；OneOS 实车事件 `NOT_TESTED` | 不绑定未知 Binder、不注册猜测权限的广播；无事件时保持用户手动映射/无动作 |
| ECARX 燃油/车辆传感器 | 星舱 `w1/RunnableC0228p0`、`w1/C0224n0` | `Car.create(...).getSensorManager()`；listener 注册/读取/释放；fuel/speed/RPM 等符号 | 调用点 `CALL_SITE_CONFIRMED`；SDK `ISensor` 原始接口和 ID 数值不完整 | 样本有 OneOS / secure-settings 等请求；ECARX 服务授权、传感器单位/范围、天际版支持情况未知 | 没有 Geely 传感器读取器；BYD 电量/SOC/车速代码不能复用 | `BLOCKED`；没有新适配测试；实车 `NOT_TESTED` | 数据缺失应为 Unknown，不回填 0，不以 SOC 冒充燃油；不读写车辆总线 |
| DIM / 仪表导航 | 星舱 `MConfigInitService`、`w1/AbstractC0221m` | `DimInteraction.create/getDimMenuInteraction/getNaviInteraction`、反射 callback 注册、`notifyTurnByTurnStarted`、presentation switch | 名称和局部 arity 的 `CALL_SITE_CONFIRMED`；完整 callback/packet 字段未确认 | 必须确认 DIM API/服务及写入权限；Manifest 请求不等于已授予；2024 天际版未知 | CarPaly 有通用导航/仪表组件，不含 Geely DIM writer | `BLOCKED`；既有通用渲染测试不算 OEM 适配；实车 `NOT_TESTED` | 不启用写入；仅在获得官方 SDK/权限后做只读能力探测 |
| HUD 导航 / 地图 Surface | 车控 2.2 Manifest、`assets/libgmhud.so` | `MapSurfaceProviderService`、`IMapSurfaceProvider`、Native `HudIpcClient` / `HudRenderHook` | Manifest 服务声明、Native 符号及字符串；非厂商 SDK 方法调用点，整体 `STRING_ONLY`/Native `SIGNATURE_CONFIRMED` | 没有系统签名、binder 描述符/安全策略及外部 app 授权证据；车型/固件未知 | 无 Geely HUD adapter；现有 BYD 输出有严格 BYD gate | `BLOCKED`；BYD 单测与本轮 gate 回归 PASS；Geely HUD `NOT_TESTED` | 不复制 `.so`、不运行 `gm_inject`、不 Hook 地图进程；失败时不发送任何命令 |
| HUD 歌词 | 星舱 `C0312g3` / dashboard media model；车控 2.2 嵌套 Dushu 插件 | `DashboardMediaLyric(text,source,updatedAtElapsedMs,staleAfterMs)`；插件 Android MediaSession | 数据模型/内部数据流可静态确认；无 OEM HUD sink，非 HUD 写入 `CALL_SITE_CONFIRMED` | 无合法 HUD 输出接口、歌词与导航/倒车优先级协议 | 无 Geely HUD 歌词实现 | `UNKNOWN`；未测试 HUD；实车 `NOT_TESTED` | 可保留应用内预览设计；不向未识别 Surface 输出 |
| OEM 音频 / 麦克风 / 原车音源 | 0914 AndroidX 字符串；车控 2.2 Dushu 插件 | 没有可确认的 Geely AudioPolicy / OEM route API | `0914 HYCarplaySWC` 是 AndroidX 字段字符串；OEM route `UNKNOWN` | 无 AudioPolicy、设备地址、系统权限或车机固件的直接证据 | CarPaly 用 Android `AudioTrack`、`AudioFocus`、`AudioAttributes`；Geely 新配置默认导航流为 `STREAM_MUSIC` | 通用音频 `IMPLEMENTED/PARTIAL`，通道映射单测通过；Geely 原车路由 `NOT_TESTED` | 只走 Android 路由和现有用户设置；导航语音、电话、Siri、mic 与扬声器待实车采集 |
| 倒车 / 360 优先级 | 五 APK 静态检查 | 未能确认稳定第三方事件/优先级契约 | `UNKNOWN` | 未知服务/权限、车机接管顺序未知 | CarPaly 不发 Geely 命令；系统安全页由宿主/车机处理 | `UNKNOWN`；无 Geely 测试 | 不遮盖、抢占或抑制原车倒车/360/安全 UI |
| 1.1 / 马大师车控 API | 两个加固 APK 的公开 Manifest/DEX 外壳 | 未恢复可用类方法 | Manifest/loader 信息；车辆调用 `UNKNOWN` | 各自 Manifest 请求多项车辆/OneOS/系统权限，但没有可验证授予 | 无代码对接 | `UNKNOWN`；没有接口测试；实车 `NOT_TESTED` | 等待厂商可审计 SDK 或完整授权资料，不破解保护层 |

## 代码侧保护现状

- `shared/src/main/java/com/shilapi/xcertplay/hud/BydNavigationOutputs.kt` 的 `start(context)` 在启动车辆输出 worker 前调用 `BydOutputSettings.vehicleOutputsAllowed`；该条件同时要求用户显式开启和 BYD 车机识别。
- `BydCarPlayCall.onFrame` 的 HUD/仪表写入也要求 `BydOutputSettings.isBydHeadUnit(app)` 和用户开关。此代码不应因字符串相似而改成 Geely。
- `WheelKeyService` 的默认 BYD wheel code 对 `GEELY_XINGYUE_L` 禁用；显式用户映射仍保留。`WheelKeyServiceTest.geelyProfileDoesNotApplyHistoricBydWheelCodesButKeepsLearnedKeys` 覆盖该回退。
- 本次新增 `BydOptionalOutputSettingsTest.geelyKx11IdentityNeverPassesTheBydVehicleWriterGate`，测试 GEELY/KX11 Build fingerprint 即使误开 BYD 开关也无法通过车辆 writer gate。它验证安全门，不证明任何 Geely 功能已连车。

## 新增样本交叉检查

| 能力 | Fake Ultra / Glauncher 新证据 | CarPaly 状态 |
|---|---|---|
| OneOS 方向盘 | 新 APK 中未找到 `IServiceManager`、`IInputManager`、`IInputListener` 或 `registerListener` 调用链 | 继续仅 Android KeyEvent/学习映射；OEM `BLOCKED` |
| ECARX 车辆传感器 | 新 APK 未发现 `ISensor`、`CarSensor`、VHAL 或已确认 `fuelPercent` provider | 无 OEM reader；只增加单位/来源/时间/有效期模型，默认无值 |
| DIM/HUD | 没有新 DIM Binder/AIDL/权限契约；Fake Ultra 的第二屏是 Android DisplayManager/Surface | OEM 输出 `BLOCKED`；不执行注入/Hook |
| HDMI2/Presentation | Fake Ultra 存在 DisplayManager/第二屏 Surface 静态调用点 | 通用 API 路径可参考，真实车机 display 映射 `NOT_TESTED` |
| Media card | Fake Ultra 有应用绘制 artwork 的线索，未找到 OneOS 原车媒体发布服务 | 复用现有 Android MediaSession，不重复建卡片；OEM sink `UNKNOWN` |
| 音频 | 两个新 APK 未发现 Geely AudioPolicy/route API | 现有 Android AudioTrack 路径，增加 playback-active 诊断；实车 `NOT_TESTED` |

完整新样本哈希、权限与调用路径分别记录于 `FAKE_ULTRA_APK_ANALYSIS.md` 和 `GLAUNCHER_APK_ANALYSIS.md`；七样本对照见 `SEVEN_APK_INTERFACE_COMPARISON.md`。

## 决策

本轮没有新增 Geely OEM 运行时代码：没有一个 OEM 接口同时满足可复现方法契约、系统授予条件及 2024 天际版适用性证据。贸然复制样本声明或按字符串绑定会把未经授权/固件私有接口变成写操作。本地 Profile、CarPlay 通用音频、BYD 保护门及用户学习键保持原样。
