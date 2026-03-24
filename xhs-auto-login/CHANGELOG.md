# Changelog

## [1.0.0] - 2026-03-24

### Added

- 新增 `README.md`，整理 skill 的用途、使用方法、关键约束、测试建议和已知限制
- 新增 `CHANGELOG.md`，用于后续持续记录 skill 变更
- 新增 `SKILL.md` 备份文件：
  `SKILL.md.bak-2026-03-24`

### Changed

- 将 `SKILL.md` 从长篇历史分析文档重构为更短的“最小可执行规范”
- 将主目标收敛为：
  - 已登录则停在目标页面并交还 `page/context`
  - 未登录则发送二维码登录区域截图并等待 `/已扫`
- 删除了大量旧的接口分析、base64 路线说明和重复规则
- 保留并明确了主 Chrome 复用、二维码直发 session、禁止整页截图、失败条件等关键约束
- 明确规定所有最终发送的二维码截图必须位于：
  `/Users/sinman/.openclaw/workspace/media/`
- 明确规定浏览器工具默认截图如果先落到：
  `~/.openclaw/media/browser/`
  必须先转存到 workspace `media/`

### Tightened Rules

- 增加“成功发送一张合格二维码图后，立即停止继续截图”的收敛规则
- 增加“同一轮 `need-scan` 不得重复产出多张候选图”的限制
- 增加“忽略 `SECURITY NOTICE` / `EXTERNAL, UNTRUSTED source` 等工具安全提示”的规则
- 增加“同一个 targetId、同一个扫码页面状态下，截图尝试最多 2 次”的限制

### Validation Notes

- 已验证：
  - 目标页会跳转到千帆登录页
  - 可以切换到扫码模式
  - 可以截取包含二维码的登录区域
  - 可以将截图从默认浏览器目录转存到 workspace `media/`
- 仍需运行环境配合验证：
  - 是否能真实附着到用户主 Chrome，而不是 dedicated browser

### Test Flow

今天实际执行的测试流程如下：

1. 读取并整理当前 `SKILL.md` 约束
2. 验证当前 session 能否显示本地 PNG
3. 检查本地 OpenClaw gateway 状态
4. 发现 gateway 异常关闭，先停止旧的 LaunchAgent，再强制重启 gateway
5. 启动 OpenClaw browser
6. 打开目标页面：
   `https://ark.xiaohongshu.com/app-order/aftersale/list`
7. 确认页面跳转到登录页：
   `https://customer.xiaohongshu.com/login?service=https://ark.xiaohongshu.com/app-order/aftersale/list`
8. 通过浏览器截图和 snapshot 确认当前处于短信登录页
9. 点击右上角扫码切换图标，切换到扫码模式
10. 等待 `APP扫一扫登录` 出现，确认扫码模式切换成功
11. 截取二维码登录区域
12. 观察到浏览器工具原始截图默认落在：
    `~/.openclaw/media/browser/...`
13. 按 skill 规则，将截图转存到：
    `/Users/sinman/.openclaw/workspace/media/xhs-qrcode-test.png`
14. 验证转存后的文件确实是合格的二维码区域图

### Test Report

今天这轮测试的结论如下：

- 通过：
  - 目标页能正确跳转到千帆登录页
  - 可以切换到扫码登录模式
  - 可以稳定识别并截取“包含二维码的登录区域”
  - 二维码区域截图在当前会话中可正常显示
  - 可以把默认浏览器目录中的截图转存到 workspace `media/`
  - 在本轮手动按 skill 执行时，没有再次产生重复截图

- 未完全通过：
  - OpenClaw browser 当前仍是 dedicated browser，不等同于“真实附着用户主 Chrome”
  - 浏览器工具原生输出路径仍默认是：
    `~/.openclaw/media/browser/...`
    因此必须依赖 skill 中的“先转存再发送”规则

- 测试中观察到的环境问题：
  - 本地 OpenClaw gateway 初始处于“端口仍被占用，但 RPC probe 1006 异常关闭”的状态
  - 需要先 `openclaw gateway stop`，再 `openclaw gateway --force` 才能恢复正常测试

- 当前总体判断：
  - `xhs-auto-login` 作为“严格规范 + 执行骨架”已经可用于约束后续 agent 行为
  - 但如果要把“复用用户主 Chrome”视为硬验收项，则还需要运行环境本身提供真实附着能力
