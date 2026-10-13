# GEELY 仪表渲染能力与应用内预览

## 样本观察

Fake Ultra SHA-256：`5b0b367d34650b029997e461b4de2fb6c1e9407636faf19bbb7a4e15a83019fd`。`GeelySelfDrawSettingsActivity.p()` 将 `self_draw_speed_enabled`、`self_draw_rpm_enabled`、`self_draw_average_fuel_enabled`、左右仪表、专辑封面和动态仪表等布尔项写入偏好。反编译可读范围内没有找到这些设置与已授权车辆 provider 的完整数据流。CarPlay Host 的第二屏 Surface 是视频/应用绘制路径，不能据此认定其控制原厂仪表。

布局路径包含多个画布/安全区域尺寸配置，且 1920×1080 display filter 与 1920×720 仪表配置同时出现；它们是 UI 布局参数，不是实车分辨率测量。

## CarPaly 实现边界

当前 CarPaly 有通用 cluster/presentation 组件，但 Geely 没有 OEM writer。新增的 `common/.../geely/GeelyVehicleData.kt` 是只读领域模型：每个样本明确来源、单位、时间戳、有效性与 freshness；Unknown/断开/拒权无值，非法/过期值不允许作为实时输入。当前没有车辆 reader、没有仪表数据绑定，也不画伪车速、转速、挡位或油量。

| 能力 | 状态 | 说明 |
|---|---|---|
| 应用内可视化样式/通用第二屏 | `PARTIAL` | 现有共享组件；没有在本轮加入另一套重复页面 |
| 动态车速/RPM/燃油 | `BLOCKED` | 缺可靠 provider、单位/范围契约和车辆权限；模型默认无读数 |
| 原厂 DIM / HUD 输出 | `BLOCKED` | 没有授权输出协议/权限 |
| 分辨率、Surface 生命周期 | `PARTIAL` | Android 通用代码存在，目标车机 `NOT_TESTED` |

未来若开发纯应用内预览，必须显示“应用内预览”，不使用虚构车辆值，支持关闭和默认布局恢复；退出或 Display 移除必须释放 Presentation/Surface。不得 Hook、注入或覆盖原车安全信息。
