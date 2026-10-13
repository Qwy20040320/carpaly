# CarPaly v1.1.51 — ECARX / OneOS 方向盘接口

## 静态确认的 OneOS Binder 契约

在 `【必装】星舱助手-v1.2.0.apk` 的 DEX 中可读到：

```text
IServiceManager.getService(int) -> IBinder       transaction 2
IInputManager.registerListener(IInputListener, String, int[]) -> void  transaction 3
IInputManager.unregisterListener(IInputListener, String) -> void       transaction 4
IInputManager.getControlIndex() -> int             transaction 5
IInputListener.onKeyEvent(int, int, int) -> void
IInputListener.onShortClick(int, int) -> void
IInputListener.onHoldingPressStarted(int, int) -> void
IInputListener.onHoldingPressStopped(int, int) -> void
IInputListener.onLongPressTriggered(int, int) -> void
IInputListener.onDoubleClick(int, int) -> void
```

OneOS 接口描述符：`com.geely.lib.oneosapi.IServiceManager`、`com.geely.lib.oneosapi.input.IInputManager`、`com.geely.lib.oneosapi.input.IInputListener`。

样本调用链：`w1/Q0.start()` -> 显式 bind `com.geely.service.oneosapi/.OneOSApiService` -> `IServiceManager.getService(8)` -> `IInputManager.Stub.asInterface(...)` -> `registerListener(listener, packageName, int[]{200400})`。`w1/N0` 在停止时调用 `unregisterListener(listener, packageName)` 并解绑；`w1/O0` 适配 Binder listener 回调到样本自己的 key handler。调用方捕获 Binder 异常，并对 service 缺失有限重试。

这里只能确认方法参数类型、部分事务号及样本调用链。整数 `8` / `200400` 的公开枚举语义、各回调参数的 key/action 对应、长按 repeat 策略及固件版本范围没有正式文档佐证，不能把它们硬编码为 CarPaly 映射。

## 广播入口的安全性

星舱 Manifest 将 `tuox.mconfig.KeysConfigReceiver` 设为 `exported=true`，没有看到 receiver 级 `android:permission`。它过滤 `ECARX_KEY_ISRC_EVENT[_DOWN/_UP]` 与 `ECARX_KEY_RSRC_EVENT[_DOWN/_UP]`。可读 `onReceive` 不读取输入 Intent 的 key-code extra；一条兼容分支会自行发出 `ECARX_KEY_RSRC_EVENT` 并设置 `ecarx.extra.ECARX_KEY_EVENT_TYPE=KeyCode.KEYCODE_R_SRC`。

由于广播入口可被外部 app 触发且缺少 receiver 权限约束，它不是可信方向盘硬件输入通道；消费它会允许伪造按键事件。CarPaly 不应复制该 exported receiver，也不应通过发送这些 action 操作车机。普通第三方调用权限和原车实际发送权限仍未知。

## 与 CarPaly 对照

- `common/src/main/java/com/shilapi/xcertplay/WheelKeyService.kt` 使用 Android Accessibility `KeyEvent` 和本地用户学习的键码，不调用 ECARX/OneOS Binder。
- `HeadUnitProfile.GEELY_XINGYUE_L` 时不套用历史 BYD 默认方向盘键码；用户显式学习/存储的 mapping 仍被读取。`WheelKeyServiceTest.geelyProfileDoesNotApplyHistoricBydWheelCodesButKeepsLearnedKeys` 已覆盖该行为。
- 本轮没有 OneOS runtime listener 适配。用户配置映射的单元测试不等于星越 L 原车能把方向盘输入送到 Android Accessibility。

## 结论与状态

| 子项 | 状态 | 下一步前置条件 |
|---|---|---|
| OneOS AIDL/回调形状 | `SIGNATURE_CONFIRMED` | 需厂商 SDK/接口版本文档解释整数和事件 |
| 星舱 OneOS 调用点 | `CALL_SITE_CONFIRMED` | 不代表权限授予 |
| 星舱广播 receiver | `CALL_SITE_CONFIRMED`，但不可信 | 不作为 CarPaly 输入源 |
| CarPaly 用户学习映射 | `IMPLEMENTED` / 自动测试通过 | 实车事件输入仍 `NOT_TESTED` |
| Geely OneOS 适配 | `BLOCKED` | 需书面 API 权限与设备侧可授予证据 |
| 2024 天际版方向盘 | `NOT_TESTED` | 驻车时记录按键与 CarPaly 诊断日志 |

安全回退：找不到服务、权限拒绝、签名不匹配、回调未知时不消费事件；保持无动作并保留用户原映射。不得卸载原车服务或改系统签名权限。

## Fake Ultra / Glauncher 复核

两份新增 APK 未发现 OneOS 管理器、方向盘 listener/AIDL、注册/注销调用点或 ECARX 输入服务。它们不增强星舱 OneOS 的权限或事件值证据。CarPaly 继续只消费 Android KeyEvent 和用户学习映射；真实方向盘到 Android 的事件注入链仍为 `NOT_TESTED`。没有补写未经确认的 key code、长按语义或 service id。
