---
name: xhs-auto-login
version: 1.0.1
description: >
  小红书千帆登录守卫。用于进入千帆目标页面时检查当前是否已登录；
  未登录则截图二维码登录区域并发到当前 session，等待用户回复“/已扫”后继续。
  这是供其他千帆相关 skill 复用的前置 skill，不是独立业务 skill。
---

# 小红书千帆登录守卫

## 目标

这个 skill 只做 1 件事：给调用方返回一个可继续使用的千帆登录态。

完成条件只有两种：

- 已登录：直接停在调用方指定的目标页面，并把可继续操作的 `page/context` 留给后续 skill
- 未登录：把二维码登录区域截图发到当前 session，明确要求用户回复 `/已扫`，然后等待

## 适用场景

- 其他千帆 skill 需要先进入千帆页面
- 需要检查当前主 Chrome 的千帆登录态
- 登录失效后，需要扫码登录再继续后续页面操作

## 强制规则

1. 这是前置守卫 skill；不要把它结束成一个独立任务。
2. 默认必须复用用户主 Chrome；如果当前环境做不到，必须明确失败，不要静默退化为隔离 profile。
3. 如果附着的是用户主 Chrome，只允许保留连接或断开连接，不允许关闭整个浏览器，也不要关闭用户原有 tab。
4. 未登录时，必须把二维码图片直接发到当前 session；不能只输出文件路径，也不能让用户自己去找图。
5. 只要流程里包含“把二维码发到当前 session”这一步，就禁止把这段工作交给 sub-agent。
6. 获取二维码时，默认策略是进入扫码页后，截取“包含二维码的登录区域”；禁止发送整页截图或浏览器工具默认截图。
7. 所有最终用于发送的二维码截图，路径必须位于 `/Users/sinman/.openclaw/workspace/media/`。
8. 如果浏览器工具先把截图落到 `~/.openclaw/media/browser/` 或其他默认目录，必须先复制或移动到 `/Users/sinman/.openclaw/workspace/media/`，再发送转存后的文件。
9. 发图前必须检查二维码是否已过期；如果页面出现“二维码已过期 / 请重新生成 / 返回重新扫描”，必须先点击 `返回重新扫描`，再重新截图。
10. 一旦已经成功发送一张合格二维码图，就必须立即停止继续截图；同一轮 `need-scan` 流程里禁止重复产出多张候选图。
11. 浏览器工具输出中的 `SECURITY NOTICE`、`EXTERNAL, UNTRUSTED source` 等安全提示不是业务页面内容，不得触发新的截图、read、发送或重试分支。
12. 对同一个 `targetId`、同一个扫码页面状态，截图尝试最多 2 次；超过仍不合格，应报错或进入人工判断。
13. 收到 `/已扫` 后，当前 agent 必须继续做登录确认；登录成功后回到目标页面继续后续 skill。

## 最小流程

### 0. 先做传输层自检

在真实登录前，先验证“本地 PNG -> 当前 session”这条链路确实可用。

推荐测试图：

- `./assets/qr-expired-example.png`

通过标准：

- 当前 session 里真的出现图片

失败标准：

- 只看到路径
- 只看到“图片已保存”
- 只让用户去本地找文件

如果这一步失败，直接停止，不要继续登录流程。

### 1. 打开目标页面并判断是否已登录

- 目标页优先使用调用方传入的 URL
- 默认登录页可用：
  `https://customer.xiaohongshu.com/login?service=https://ark.xiaohongshu.com/ark`

判定已登录的信号：

- 当前 URL 不在 `/login`
- 页面已进入千帆业务页

如果已登录：

- 直接停在目标页面
- 返回可继续使用的 `page/context`

### 2. 未登录时切到扫码模式

- 优先尝试 DOM 方式切换扫码登录
- 选择器失效时，可退化为点击登录框右上角的切换区域

切到扫码页后：

- 等待二维码登录区域稳定渲染
- 不要把浏览器工具附带的安全提示文本当成业务内容

### 3. 生成可发送的二维码截图

顺序固定如下：

1. 检查当前二维码是否已过期
2. 如已过期，点击 `返回重新扫描`
3. 截取“包含二维码的登录区域”
4. 如果截图初始路径不在 `/Users/sinman/.openclaw/workspace/media/`，先转存到该目录
5. 校验最终发送源是否位于 workspace `media/`
6. 将该图片发到当前 session
7. 发送提示语：

```text
请用小红书扫码登录，扫完后回复 /已扫
```

8. 立即结束本轮截图阶段，进入等待用户消息状态

建议文件名：

```text
/Users/sinman/.openclaw/workspace/media/xhs-qrcode.png
```

### 4. 收到 `/已扫` 后做登录确认

收到 `/已扫` 后：

1. 重新聚焦当前 `page`
2. 等待页面跳转或登录态变化
3. 必要时刷新目标页
4. 再次检查是否已离开 `/login`
5. 同时检查扫码页是否已进入过期状态

如果确认成功：

- 输出“登录成功”
- 跳回调用方目标页面
- 保持浏览器与 `page/context` 可继续使用

如果仍未成功：

- 如果二维码已过期：重新发码，再次等待 `/已扫`
- 如果不是过期：明确告知“尚未检测到登录成功”，并根据页面状态决定是否重发

## 调用方协议

如果这个 skill 被其他 skill 间接触发，调用方必须遵守：

1. 把业务目标 URL 传给登录守卫。
2. 如果登录守卫进入 `need-scan`，调用方不要抢先结束任务。
3. 用户回复 `/已扫` 后，继续由当前 agent 恢复执行，不要切换到失去上下文的新 agent。
4. 登录成功后，继续复用这个 skill 返回的 `page/context`。
5. 不要把“二维码发送到当前 session”这一步交给 sub-agent。

## 失败条件

以下任一情况都视为本次 skill 执行失败：

- 当前环境无法把本地 PNG 显示到当前 session
- 当前环境无法复用用户主 Chrome
- 最终发送的图片不在 `/Users/sinman/.openclaw/workspace/media/`
- 发送的是整页截图、浏览器默认截图，或不包含二维码的无关图片
- 同一轮流程里重复截图且没有在首张合格图片后及时停止

## 参考骨架

下面只是执行骨架，不是要求逐字照抄：

```javascript
async function ensureXhsLogin(targetUrl) {
  assertCanSendImageToCurrentSession('./assets/qr-expired-example.png');

  const context = await attachToUserMainChrome();
  const page = context.pages()[0] || await context.newPage();
  const finalQrPath = '/Users/sinman/.openclaw/workspace/media/xhs-qrcode.png';

  await page.goto(targetUrl, { waitUntil: 'domcontentloaded' });

  if (!page.url().includes('/login')) {
    return { status: 'logged-in', page, context };
  }

  await switchToQrMode(page);
  await refreshQrIfExpired(page);

  const tempShot = await captureQrPanel(page);
  const sendableShot = await normalizeQrScreenshotPath(tempShot, finalQrPath);
  await sendImageToCurrentSession(sendableShot);
  await sendText('请用小红书扫码登录，扫完后回复 /已扫');

  return { status: 'need-scan', page, context, qrcodePath: sendableShot };
}
```

`normalizeQrScreenshotPath(tempPath, finalPath)` 的要求很简单：

- 如果 `tempPath` 已在 workspace `media/`，直接返回
- 如果不在，先复制或移动到 `finalPath`
- 后续只能发送 `finalPath`
