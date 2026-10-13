# GEELY 媒体卡片与封面路径

## 两份新增样本

Fake Ultra（`io.dushu.car`，SHA-256 `5b0b367d34650b029997e461b4de2fb6c1e9407636faf19bbb7a4e15a83019fd`）的可读 CarPlay Host 路径可将 artwork 回调交给第二屏应用绘制层；仪表配置中也有 album-art 偏好。此处没有确认 OneOS media-card publisher、DIM 卡片 Binder、标准化原车媒体服务或歌词 sink。动态仪表开关与真实车辆数据并未形成可确认闭环。

Glauncher（`com.maxinf.car`，SHA-256 `bbbbb4fdcdc784a53c88cf7605a8a3c35be442068ee06d1e3db583541c337dcd`）只提供包列表启动和系统栏/包变更行为；没有 MediaSession/MediaMetadata/Bitmap/OneOS 媒体调用链。

前五个样本仍以星舱的 dashboard media model 和车控 2.2 嵌套 Dushu MediaSession 为线索。媒体元数据/封面读取与 OEM 仪表发布是两件事；未发现公开可调用的 OEM sink。

## CarPaly 现有实现复用

CarPaly 已经有 CarPlay 媒体元数据/MediaSession 管线，覆盖标题、歌手、专辑、播放状态、进度、来源应用与受限大小的 artwork，并在会话关闭时清理旧状态。它服务 Android/CarPaly 媒体呈现，不代表 GEELY 原车媒体卡片。因已存在完整通用能力，本轮未创建重复的媒体模型或卡片页面，也未导入第三方图片/源码。

状态：Android 媒体元数据 `IMPLEMENTED`（以现有软件测试为准）；Fake Ultra app-drawn artwork 静态路径 `CALL_SITE_CONFIRMED`（仅样本）；OneOS/OEM 媒体卡片 `UNKNOWN/BLOCKED`；星越 L 实车媒体卡片 `NOT_TESTED`。
