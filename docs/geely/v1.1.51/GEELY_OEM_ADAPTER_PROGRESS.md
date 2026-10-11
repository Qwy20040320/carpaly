# GEELY OEM 适配层进度

## 已有边界

CarPaly 当前 `GeelyVehicleAdapter` 只基于可见 Build identity/Profile 做保守识别与回退；不是 ECARX 或 OneOS 客户端。方向盘仍由 Android `KeyEvent` 与用户学习映射处理；Geely 不应用历史 BYD 默认键码，GEELY profile 不会通过 BYD 车辆写入门。Vehicle-data reader、Geely DIM/HUD writer、OneOS Binder listener 均未启用。

## 本轮新增

- `common/src/main/java/com/shilapi/xcertplay/geely/GeelyVehicleData.kt`：独立只读值模型，携带来源、明确单位、epoch 时间戳、validity 和 stale window；未知/断连/拒权/不支持没有数值，非法/超范围变为无值 INVALID，超过 freshness window 变 STALE。
- 单元测试覆盖缺值不伪造为 0、时间戳 freshness、非有限/超范围速度、燃油单位范围、RPM、未知挡位、断连及拒权。
- 音频真实 playback start 时增加低开销路由诊断：audioType、映射 channel、AudioTrack 状态/会话、usage、输出设备类型和 underrun 数。日志不记录设备名称、地址、账号或认证数据；查询异常被隔离，不改变播放。
- Release builder 使用 `--no-daemon`，使签名环境变量不进入复用的常驻 Gradle daemon。

## 仍未启用的 OEM 接口

Fake Ultra 与 Glauncher 没有新增有效 OneOS/ECARX/DIM API 契约。方向盘服务 id、传感器 ID、导航回调 payload 和 HUD writer 都不得从名称、默认 display id 或别的 APK 推断。正式 OEM SDK/权限范围缺失时，运行时状态应为 `UNSUPPORTED`、`PERMISSION_DENIED` 或 `UNKNOWN`，而非无限重试。

| 子系统 | 代码 | 自动测试 | 实车 |
|---|---|---|---|
| Geely Build/Profile | 已有保守识别 | 已有 Profile 测试 | `NOT_TESTED` |
| 方向盘 | Android KeyEvent + learned mapping；没有 OEM listener | 现有 mapping/lifecycle 测试 | `NOT_TESTED` |
| 车辆遥测 | 新数据模型，无 provider | 新 common 单元测试 | `NOT_TESTED` |
| DIM/HUD | 无 Geely writer；通用 Android display 路径仍隔离 | 现有通用显示测试 | `NOT_TESTED` |
| 音频 | 现有 AudioTrack/Focus；本轮只新增实际播放时的诊断 | 后续完整 CI 验证 | `NOT_TESTED` |

本轮不改 v1.1.4、不改版本台账、不合并 main、不创建标签或 Release。
