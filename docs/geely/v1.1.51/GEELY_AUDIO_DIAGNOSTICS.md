# GEELY / CarPlay 音频诊断

## 现有软件行为

CarPaly 已为 CarPlay 建立分流的 AudioTrack，按照媒体、导航、电话和 assistant 类型选择 Android AudioAttributes/可选 legacy stream；导航与音乐可走同一 PCM/AudioTrack sink 基础设施，AudioFocus 管理器对通话/媒体的焦点策略独立处理。KX11 首装导航默认使用 `STREAM_MUSIC`，显式用户偏好优先。构建/单测不能证明车机 AudioPolicy 把流接到正确扬声器。

## 本轮诊断改动

只有在 `AudioTrack.play()` 被调用后，新增 `Audio: playback active` 诊断快照，记录 `audioType`、解析后的 channel、track/play state、session id、AudioAttributes usage、Android output device type 与 underrun count。没有读取/记录设备名称或 address；设备路由查询失败不会中断音频。既有输入格式、AudioFocus 选择、buffer、写入和设备策略不变。导航语音问题仍需车上对照 media/nav/phone/Siri 和 AudioPolicy/AudioFlinger 实测。

只读驻车采集脚本 `scripts/collect-geely-readonly-diagnostics.ps1` 由用户先启动测试连接，再采集 `dumpsys audio_flinger`、`audio_policy`、`media_session`、目标进程 logcat。运行前应确认 ADB 目标是 CarPaly 车机并停稳车辆；脚本不写系统服务、不读取认证文件。报告中附加设备序列号/IP 等日志前请先脱敏。

| 场景 | 当前软件状态 | 车机结果 |
|---|---|---|
| 音乐 | AudioTrack/stream 代码已实现，用户先前报告音乐播放正常 | 用户对单辆车的历史反馈；当前提交未独立复测 |
| 导航播报 | 类型映射、默认/偏好路由和启动诊断已实现 | 已知此前无声，当前 `NOT_TESTED` |
| 电话 / Siri / 麦克风 | 通用流、focus、capture uplink 代码存在 | `NOT_TESTED` |
| 原厂 speaker / AudioPolicy | 无 Geely OEM route API 证据 | `NOT_TESTED` |

不声称导航音频已经修复；后续以实车抓取的 stream usage、focus、routed-device type、写入/播放头推进和 underrun 数据做定位，同时确认音乐仍可播放。
