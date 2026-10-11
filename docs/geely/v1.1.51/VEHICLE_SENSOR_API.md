# CarPaly v1.1.51 — ECARX 车辆传感器接口

## 星舱 APK 中可追踪的传感器代码

`w1/RunnableC0228p0` 的数据路径如下：

```text
Car.create(context).getSensorManager()
  -> ISensor.registerListener(listener, sensorId[, rate])
  -> ISensor.ISensorListener callbacks
  -> app model/UI update
  -> unregisterListener(listener)
```

`w1/C0224n0` 可确认的回调形式：

```text
onSensorEventChanged(int sensorId, int eventValue)
onSensorValueChanged(int sensorId, float value)
onSensorSupportChanged(int sensorId, FunctionStatus status)
```

静态代码引用 `SENSOR_TYPE_FUEL_LEVEL`、`SENSOR_TYPE_CAR_SPEED`、`SENSOR_TYPE_RPM`、`SENSOR_TYPE_GEAR`、`SENSOR_TYPE_IGNITION_STATE`、`SENSOR_TYPE_ENGINE_OIL_LEVEL`、温度与乘员状态等类型；另有未命名整型 `1055232`。APK 中没有恢复出 `ISensor`/`ISensorEvent` 官方接口定义及常量数值映射，因此这些符号名不能转成 CarPaly 可用的固件 ID。

样本在展示前将燃油浮点值除以 1000，将车速浮点值乘以 3.6；RPM 会过滤 NaN/Infinity。代码还会尝试普通和带采样参数的 `registerListener` overload，读事件和最新值，并对异常做回退。单位换算和值域来自样本 UI 行为，不等于厂商规格；其 `0.0` 回退可能把读取失败显示成有效零值，CarPaly 不复制这种行为。

## 权限、VHAL 与车型适用性

星舱 Manifest 请求 `geely.oneos.permission.SERVICE`、`WRITE_SECURE_SETTINGS` 等能力，但无车机系统对这些权限的实际 grant、签名级别和 Sensor 服务授权记录。样本代码还存在独立 OneOS 输入 Binder 路径与 RPM/VHAL 读数相关类；目前看不出 OneOS input 与 ECARX sensor manager 共用一个授权通道。2024 天际版/不同年款具体传感器支持集没有设备侧调用日志，保持未知。

## CarPaly 现状与安全决策

CarPaly 尚无 Geely Fuel/ECARX sensor adapter。现有 `BydBatteryStatus`、`BydWheelSpeedSource` 是 BYD/ADB 路径，不得改名或复用成 Geely 油量/车速。当前未向车机读取此类传感器，也未发送 CAN/UDS/VHAL 写操作。

| 项目 | 状态 | 理由 |
|---|---|---|
| 符号名称 / 类调用链 | `CALL_SITE_CONFIRMED` | 星舱 DEX 可见，SDK 定义未恢复 |
| Sensor ID 数值和速率枚举 | `UNKNOWN` | 常量所有者接口不在可恢复源码中 |
| 燃油单位/容量/有效值域 | `UNKNOWN` | 除样本 `÷1000` 显示转换外无规范 |
| `FunctionStatus` 权限/错误语义 | `UNKNOWN` | 具体 service/device 未运行 |
| 普通第三方可访问性 | `BLOCKED` | 需正式 SDK/授权和目标系统 grant |
| CarPaly Geely 传感器读数 | `NOT_SUPPORTED`（当前版本） | 没有实现，不能显示伪造值 |
| 实车数据验证 | `NOT_TESTED` | 未连接 2024 天际版 |

## 允许继续的下一步

取得针对目标固件的官方 ECARX SDK/权限说明后，先实现只读能力检查：服务不存在、权限拒绝、unsupported、NaN/Infinity、超时及陈旧值一律显示“未知”；只有收到有效 callback 且单位/范围由文档确认后才显示读数。以驻车日志证明数据来源和变化，不使用模拟值作为车辆数据，不从 APK 注入代码推测 ID。

## 新样本与安全数据模型

Fake Ultra 与 Glauncher 均未增加可复用的 `ISensor`/VHAL/车辆速度、转速、燃油或挡位读取调用链。CarPaly 新增 `common/.../geely/GeelyVehicleData.kt` 的领域模型，但未增加 provider：样本类型区分 km/h、燃油百分比、RPM 与挡位；宽松的 0–350 km/h、0–100%、0–20,000 RPM 仅是拒绝损坏数据的本地防御性边界，不是 Geely/ECARX 规格。每条有效值必须有非 UNKNOWN 来源、非负时间戳和正 freshness window。拒权、断连、不支持及 UNKNOWN 均不含值；非法输入不保留数值，过期读数变为 `STALE` 且 `isUsableAt=false`。单测不使用伪造值接入 UI；它只验证模型边界，不验证 ECARX 或任何实车读数。
