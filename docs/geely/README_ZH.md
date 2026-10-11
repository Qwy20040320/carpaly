# CarPaly 吉利星越 L / KX11 适配状态

CarPaly 源自 [DiPlay](https://github.com/shihabal3amri/DiPlay)，保留 GPL-3.0 许可证、原项目版权声明和上游同步能力。当前 GitHub 开发 PR 为 #6；本页只记录已核实的公开状态，不把候选配置或自动化测试描述成车辆兼容认证。

## 版本状态

- `v1.1.4`（code 36）和旧格式 `v1.1.5`（code 37）均有历史公开预发布记录；历史附件保持不变。
- `versionCode=38` 已从本地历史构建观察到。当前目标 `v1.1.51` / Android `versionCode=39` 尚无 APK、标签或 Release，版本号无冲突。
- 所有今后的用户 APK 都必须是固定签名的 Release 构建，唯一命名格式为 `CarPaly-XingyueL-v{versionName}.apk`；CI 内 Debug APK 仅供内部验证，不作为下载产物。
- 只有 v1.1.51 Release APK 实际校验、交付并登记 SHA-256 后，才分配 `v1.1.52` / code 40；`v1.1.6` 的 code 必须高于所有既往版本。

## 吉利车型状态

2024 款星越 L 天际版是优先测试目标；2021、2022、2023、2024、2025、2026 年款和 KX11 Generic 均为候选 profile，实车均为 `NOT_TESTED`。源码和合成身份单测不代表车机读数或实车兼容。用户反馈 v1.1.4 曾在一辆星越 L 上连接 CarPlay 且音乐可播放，但连接模式和完整车辆配置未记录，维护者未独立复现；导航播报无声和顶部状态栏遮挡仍为待回归问题。

GEELY 标签与吉利图标是车辆按钮默认值。方向盘按键、HUD、仪表、燃油、原车音频/麦克风、倒车和 360 接管均未取得足以确认星越 L OEM 方法与权限的证据，未验证功能保持关闭或未实现；不得向车辆控制总线发送猜测命令。

本轮七 APK 交叉结论与实现边界见[接口提取报告](v1.1.51/APK_INTERFACE_EXTRACTION.md)、[OEM 接口矩阵](v1.1.51/GEELY_OEM_API_MATRIX.md)、[新增样本分析](v1.1.51/FAKE_ULTRA_APK_ANALYSIS.md)、[第二屏分析](v1.1.51/GEELY_HDMI2_DISPLAY_ANALYSIS.md)、[媒体卡片分析](v1.1.51/GEELY_MEDIA_CARD_ANALYSIS.md)、[车辆数据模型](v1.1.51/VEHICLE_SENSOR_API.md)和[实车测试计划](v1.1.51/GEELY_VEHICLE_TEST_PLAN.md)。只有 `config/public-markdown-allowlist.json` 精确列明的报告可公开提交；聊天截图、认证材料、车辆日志和临时分析输出留在本地私有目录。

请查看[根目录 README](../../README.md) 获取当前功能矩阵、安装和安全说明。
