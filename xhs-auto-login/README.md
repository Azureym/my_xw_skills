# xhs-auto-login

## 用途

`xhs-auto-login` 是一个小红书千帆登录守卫 skill。

它只负责一件事：在调用方进入千帆目标页面前，确保当前浏览器具备可继续使用的登录态。

完成结果只有两种：

- 已登录：直接停在目标页面，并把可继续操作的 `page/context` 留给后续 skill
- 未登录：截图二维码登录区域，发送到当前 session，等待用户回复 `/已扫`

这个 skill 设计为其他千帆相关 skill 的前置步骤，不是独立业务 skill。

## 当前行为

当前版本的默认行为如下：

1. 先验证“本地图片是否能真的显示到当前 session”
2. 打开调用方目标页面
3. 如果页面已经登录，直接放行
4. 如果未登录，切换到扫码模式
5. 截取“包含二维码的登录区域”
6. 如果浏览器工具先把截图落到 `~/.openclaw/media/browser/`，先转存到 `/Users/sinman/.openclaw/workspace/media/`
7. 发送转存后的二维码截图到当前 session
8. 提示用户回复 `/已扫`
9. 收到 `/已扫` 后继续确认登录
10. 登录成功后回到目标页面，并把 `page/context` 继续交给后续 skill

## 使用方法

### 作为前置 skill 调用

调用方应提供业务目标 URL，例如：

```text
https://ark.xiaohongshu.com/app-order/aftersale/list
```

调用时应满足以下约定：

1. 传入目标页面 URL
2. 如果返回 `need-scan`，不要结束当前任务
3. 用户回复 `/已扫` 后，继续由当前 agent 恢复执行
4. 登录成功后，继续复用这个 skill 返回的 `page/context`

### 用户侧表现

如果未登录，用户应该看到：

- 当前 session 中真的出现二维码图片
- 一句提示语：

```text
请用小红书扫码登录，扫完后回复 /已扫
```

## 关键约束

当前版本保留的核心规则如下：

- 默认必须复用用户主 Chrome；做不到就明确失败
- 不允许关闭用户主 Chrome
- 不允许把二维码发送交给 sub-agent
- 禁止发送整页截图
- 最终发送的二维码图路径必须在 `/Users/sinman/.openclaw/workspace/media/`
- 浏览器默认截图若先落到 `~/.openclaw/media/browser/`，必须先转存到 workspace `media/`
- 发图前必须检查二维码是否过期
- 成功发送一张合格二维码图后，必须立即停止继续截图
- `SECURITY NOTICE` 等浏览器工具安全提示不是业务内容，不得触发重试分支
- 对同一页面状态，截图尝试最多 2 次

## 当前文件结构

```text
xhs-auto-login/
├── SKILL.md
├── SKILL.md.bak-2026-03-24
└── assets/
    └── qr-expired-example.png
```

## 测试建议

后续修改这个 skill 时，建议至少检查以下几项：

1. 能否先通过本地图片显示自检
2. 能否进入目标页面并正确判断登录态
3. 未登录时是否能成功切到扫码模式
4. 是否只截取二维码登录区域，而不是整页
5. 最终发送源是否位于 `/Users/sinman/.openclaw/workspace/media/`
6. 是否会重复截图
7. 是否会错误处理 `SECURITY NOTICE`
8. 登录成功后是否仍停留在目标页面，并保留 `page/context`

## 当前已知限制

- skill 文档要求“默认复用用户主 Chrome”，但这依赖运行环境本身具备附着到主 Chrome 的能力
- OpenClaw 浏览器工具当前默认仍可能先把截图写到 `~/.openclaw/media/browser/`，所以执行时必须显式做转存
- 这个 skill 当前更像“严格规范 + 参考骨架”，而不是完整自动化实现代码
