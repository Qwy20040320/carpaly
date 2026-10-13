# Fake Ultra 第二屏 / “HDMI2”分析

## 结论先行

样本实现可确认的是 Android `DisplayManager` 枚举、非默认外接显示器筛选、Presentation/Surface 生命周期以及 CarPlay 视频 Surface 转交。字符串 `HDMI2` 和默认 display id 2 不是对 2024 星越 L 天际版物理 HDMI、原厂仪表或 HUD 的验证。CarPaly 不复制样本工厂模式副作用，也没有 Geely 输出启用。

## 静态路径

样本 `GeelyCarPlay_Fake Ultra_by_stonezzz.apk` SHA-256：`5b0b367d34650b029997e461b4de2fb6c1e9407636faf19bbb7a4e15a83019fd`。`defpackage.v3.m(Context,int): tb0` 使用 `Context.getSystemService(DisplayManager)`，并检查品牌/OEM包名线索、display id、default display 排除和 1920×1080 尺寸。`v3.n(Context)` 由 `geely_cluster_safe_area/display_id` 偏好给出默认 id 2。`defpackage.lb0` 管理 `DisplayListener`，重建 `xa0` 显示对象，监听 surface available/gone；CarPlay Host 将 Surface 传入 `u7.b(111, Surface)`。关闭或屏幕消失会走 stop/release 回调。

日志字符串 `Cluster: HDMI2 presentation ready displayId=...` 与 `Cluster: secondary video stream stopped` 与该路径相符；它们是样本日志，不是本车日志。筛选器和设置布局同时出现 1920×1080、1920×720 等参数，面板实际逻辑分辨率/安全区必须在车辆上测量。

## 实现路线与状态

| 路线 | 当前证据 | CarPaly 状态 |
|---|---|---|
| Android 第二屏 Presentation | 公共 `DisplayManager` 可枚举外接显示器 | 通用 Cluster/副屏路径已存在；Geely 输出未实车验证 |
| Geely DIM/HUD OEM 服务 | 新样本未给出服务描述符、方法契约或授权 | `BLOCKED`，不调用 |
| 注入/Hook/工厂模式 | Fake Ultra 有 `qb0.c(3/1)` 未知副作用，车控 2.2 有内部 Hook 线索 | 禁止复制或执行 |

CarPaly 当前未新增第二套副屏显示器；保留现有通用 Presentation 与显示安全区。可进行的驻车实车检查应记录 `DisplayManager` display id、尺寸、flags、presentation support、Surface 创建/销毁和复连，不采集用户身份信息，也不更改原厂模式。失败时只结束副屏会话，不能影响 CarPlay 主屏或原车安全显示。
