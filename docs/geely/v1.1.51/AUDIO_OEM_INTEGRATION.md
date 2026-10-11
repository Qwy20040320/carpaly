# CarPaly v1.1.51 — 音频与原车路由证据

## 五个样本的发现

`0914.apk` Manifest 请求 `RECORD_AUDIO`、`MODIFY_AUDIO_SETTINGS`、`ACCESS_NOTIFICATION_POLICY` 及 ECARX/Android Car 权限，说明它申请了麦克风、音频设置和通知策略相关能力；主应用逻辑受 BaiduProtect 阻碍。字符串 `HYCarplaySWC` 位于 AndroidX `MediaSessionCompat` 兼容类字段，没有应用层调用点，不能据此推断它有 ECARX AudioPolicy 或已授权的原车音频服务。

星越 L 车控 2.2 的内嵌 Dushu 插件用 Android `MediaSession`、Notification Listener 和 `AudioManager.dispatchMediaKeyEvent` 一类通用能力定位/控制媒体 app；没有发现导航提示音、电话、Siri、蓝牙麦克风或 Geely 原车 source 切换的 OEM 路由契约。星舱助手能展示歌词/媒体状态，也没有将 CarPlay PCM 路由至指定 OEM 设备的可审计实现。

所以 OEM 音源切换、AudioPolicy usage 映射、扬声器设备地址、导航 Ducking、通话/Siri 通道和麦克风输入选择均为 `UNKNOWN`；样本的权限声明或实车用户反馈不是可复现的接口证据。

## CarPaly 当前 Android 音频路径

- `shared/src/main/java/com/shilapi/xcertplay/media/AndroidMediaSink.kt` 创建 Android `AudioTrack`，维护 AudioFocus 生命周期，并按 CarPlay 类型和可选用户覆盖设置 AudioAttributes/legacy stream。
- `shared/src/main/java/com/shilapi/xcertplay/media/AudioChannelMapping.kt` 将 `media`、`default/alert/compatibility`、`telephony`、`speechrecognition` 分别映射为 media、navigation、phone、assistant 类别；导航类别使用 speech content / navigation usage，独立 channel override 可切换 legacy stream。
- `common/src/main/java/com/shilapi/xcertplay/AirPlayPersistence.kt` 对首次使用的 Geely Profile 将导航音频 fallback 设为 `AudioManager.STREAM_MUSIC`；明确保存的用户选择优先，显式 0 可回到 usage-based route。
- 该策略让导航音频请求沿 Android media route，目的是针对“音乐响、导航提示无声”的用户报告；它没有厂商设备路由/ducking 保证。Siri、电话、导航、麦克风与原车音频回退都仍须实车验证。

## 验证矩阵

| 功能 | 当前静态/自动状态 | 2024 天际版实车状态 |
|---|---|---|
| CarPlay Media/Navigation/Phone/Assistant 分类 | `IMPLEMENTED`；映射、持久化和 AudioTrack/Focus 生命周期已有自动测试 | `NOT_TESTED`（对当前 1.1.51 提交无运行时证据） |
| Geely 首次安装导航 `STREAM_MUSIC` fallback | `IMPLEMENTED`；持久化测试已有 | `NOT_TESTED`；不保证车机接受该 route |
| Geely OEM AudioPolicy / 原车音源 | `UNKNOWN` | `NOT_TESTED` |
| CarPlay 音乐出车机扬声器 | 用户曾反馈旧版本音乐正常；非当前构建测量 | `NOT_TESTED`（v1.1.51） |
| 导航播报、ducking 与恢复 | 无实车通路证据 | `NOT_TESTED` |
| Siri/电话双向音频与麦克风 | 无 Geely OEM 路由接口 | `NOT_TESTED` |

## 安全回退

不要调用样本中找不到的 AudioPolicy hidden API，不强制切换原车 source，不声明不存在的输入设备。不改变 CarPlay 已有通用 AudioFocus 管理来伪造“导航已修复”。没有 `AudioDeviceInfo` / OEM route 的受支持契约时，使用 Android 默认设备选择，并保留用户配置的 route 选项；测试录音或电话时车辆必须驻车。

## 新样本与诊断变化

Fake Ultra/Glauncher 未增加任何可确认的 Geely AudioPolicy、原车音源切换或扬声器路由 API。CarPaly 在现有 `AndroidMediaSink.startPlayback()` 真正调用 `AudioTrack.play()` 后记录 channel/type、track/play state、session、AudioAttributes usage、Android routed-device type 与 underrun 数；不记设备名称/address，读取失败不会影响播放。现有 KX11 首装导航 `STREAM_MUSIC` 策略和用户覆写保持不变。本日志只是观察 Android 路由，不证明 OEM 输出；当前导航无声仍需实车采集定位，音乐/Siri/电话/麦克风亦为 `NOT_TESTED`。
