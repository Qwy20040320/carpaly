# 七 APK 接口交叉对照

本表沿用五个既有样本的哈希、签名和证据结论，并补入 Fake Ultra、Glauncher 两份新样本；不重复反编译旧 APK。`CALL_SITE_CONFIRMED` 只代表样本中的静态调用点可读，不代表目标车机向 CarPaly 授权。全表没有 `RUNTIME_VERIFIED` 项。

| 样本 | OneOS 方向盘 | ECARX 传感器 | DIM/仪表 | HUD/第二屏 | 媒体卡片 | 原车音频 |
|---|---|---|---|---|---|---|
| `0914.apk` | 未确认；字符串不能作接口 | 未确认 | 未确认 | 未确认 | AndroidX `HYCarplaySWC` 字符串无应用调用点 | OEM 音频接口未确认；主业务受保护 |
| 星越 L 车控 1.1 | 加固外壳，`UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| 星越 L 车控 2.2 | 未确认 | 未确认 | exported `MapSurfaceProviderService` 声明，但无闭合客户端契约 | Native Hook/渲染内部线索；非公开 SDK | 嵌套 Dushu MediaSession 代码，未见 OneOS 发布 sink | Android 媒体服务，不是 Geely AudioPolicy 证据 |
| 星舱助手 1.2.0 | OneOS `IInputManager` 签名和注册调用点 `CALL_SITE_CONFIRMED`；权限/服务授权未知 | ECARX sensor 订阅调用点可见，ID/单位/授权不完整 | DIM 初始化及反射方法名可见，回调契约不完整 | 未确认可授权 HUD writer | 有 dashboard media model 线索，无已确认 OEM sink | OEM 路由未确认 |
| 马大师车机助手 0.5.1 | 加固外壳，`UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| Fake Ultra 0.3.2 | 本次搜索未发现 OneOS 管理器/监听调用 | 未发现 ECARX sensor provider | 未发现 DIM SDK/写入接口 | Android DisplayManager + Surface 第二屏 app 路径 `CALL_SITE_CONFIRMED`；OEM 映射未确认 | CarPlay artwork 回调/应用内偏好线索，无 OneOS 发布接口 | 未发现 OEM AudioPolicy |
| Glauncher 1.0 | 未发现 | 未发现 | 未发现 | 通用启动器/系统栏代码 | 未发现 | 未发现 |

## 七样本交集结论

- 可复现的方向盘接口证据仍来自星舱助手，而非两份新增样本。其方法/transaction 可见，服务安装身份与 permission grant 未证实；CarPaly 仅保留 Android KeyEvent 和用户学习映射。
- Fake Ultra 第二屏沿 Android 公共显示 API 工作；样本声称的 HDMI2 字样不提供物理屏映射、原厂显示权限或 DIM/HUD 协议。
- 只有星舱样本能支撑 ECARX sensor 调用点线索；新样本不增加可靠 sensor ID、单位或授权证据。
- 没有样本给出普通第三方可合法调用的 Geely OEM AudioPolicy/媒体卡片接口。
- 两个样本相同签名指纹只说明它们使用相同样本签名者，不能用于身份、发布者或 OEM 关系核验。

## CarPaly 对照与安全边界

CarPaly 继续用 Android `AudioTrack`/`AudioFocus`、MediaSession、通用 `DisplayManager` 支持现有功能；GEELY Build/Profile 探测、BYD writer 隔离、系统栏安全区域与通用 CarPlay 链路均不因此变成 OEM 直连。所有真实车辆读取/写入、OneOS listener、DIM/HUD 输出都保持禁用或未实现，直到有正式 SDK、明确的 permissions/protectionLevel、设备/固件范围及可运行验收。
