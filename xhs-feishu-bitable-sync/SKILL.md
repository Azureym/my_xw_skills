---
name: xhs-feishu-bitable-sync
description: 抓取指定小红书 URL 列表并同步到指定飞书多维表格（Bitable）。当用户提出“抓取小红书页面数据并更新到飞书表格/多维表格”或类似语义时使用。先检查 lark-cli 是否安装与授权，再执行项目内 scripts/xhs_scrape_cdp.py 完成抓取与附件上传；若多维表格缺少必要字段则自动创建后再写入。
---

# xhs-feishu-bitable-sync

按以下顺序执行。

## 0. 资源导航（先读）

- 快速执行路径：`references/quickstart.md`
- 完整参数与注意事项：`references/README.MD`
- 实际执行脚本：`scripts/xhs_scrape_cdp.py`

执行时优先参考 `references/quickstart.md` 的命令模板，再根据用户要求调整参数。

## 1. 输入要求

从用户请求中提取：

- 小红书 URL 列表（单条或多条）
- 飞书多维表格 wiki 链接（必须是 bitable）

若用户未提供 URL 列表文件，创建临时文本文件（每行一个 URL）供脚本使用。

## 2. 前置检查（必须）

### 2.0 检查 Python3 是否可用

执行：

```bash
python3 --version
```

若失败，先引导用户安装 Python3 后再继续。建议引导：

- macOS（Homebrew）：

```bash
brew install python
python3 --version
```

- Ubuntu / Debian：

```bash
sudo apt update
sudo apt install -y python3 python3-venv
python3 --version
```

- Windows（winget）：

```powershell
winget install Python.Python.3.12
python --version
```

只有确认 `python3` 可执行后，才继续后续步骤。

### 2.1 检查飞书 CLI 是否安装

执行：

```bash
lark-cli -v
```

若失败，提示并引导用户安装：

- 安装文档：https://open.feishu.cn/document/no_class/mcp-archive/feishu-cli-installation-guide.md

可直接给出分平台安装示例：

- macOS（Homebrew）：

```bash
brew install lark-cli
lark-cli -v
```

- Linux（npm）：

```bash
npm install -g @larksuiteoapi/lark-cli
lark-cli -v
```

- Windows（npm）：

```powershell
npm install -g @larksuiteoapi/lark-cli
lark-cli -v
```

### 2.2 检查登录与授权

执行：

```bash
lark-cli auth status
```

若未登录或缺少关键权限，提示用户执行：

```bash
lark-cli auth login --scope "wiki:node:read base:record:create base:record:read base:record:update base:field:read base:field:create drive:file:upload"
```

## 3. 环境检查（抓取依赖）

确保 Chrome CDP 可用：

```bash
export CLAUDE_SKILL_DIR=/Users/sinman/.agents/skills/web-access
node "$CLAUDE_SKILL_DIR/scripts/check-deps.mjs"
```

如果提示 Chrome 未连接，要求用户在 `chrome://inspect/#remote-debugging` 开启 remote debugging。

## 4. 解析目标多维表格

### 4.1 从 wiki 链接解析 bitable

调用：

```bash
lark-cli api GET /open-apis/wiki/v2/spaces/get_node --params '{"token":"<wiki_token>"}'
```

确认：

- `obj_type == bitable`
- 取 `obj_token` 作为 `app_token`

### 4.2 使用用户提供的 table id

从 wiki 链接 query 中读取 `table=<tbl...>` 作为 table id。

## 5. 字段检查与自动创建

期望字段（字段名必须一致）：

- `序号`（可选，不写入也可正常运行）
- `url`
- `标题`
- `正文`
- `tag`
- `点赞`
- `收藏`
- `评论`
- `转发`
- `作者`
- `发布时间`
- `图片数`
- `图片URL`
- `获取时间(UTC)`（写入北京时间，格式：`YYYY-MM-DD HH:MM:SS`）
- `图片附件(多图)`（附件字段）

先读取字段：

```bash
lark-cli api GET /open-apis/bitable/v1/apps/<app_token>/tables/<table_id>/fields
```

对缺失字段执行创建：

- 文本字段（type=1）
- 数字字段（可选，当前默认文本兼容）
- URL 字段（type=15）
- 附件字段（type=17，用于 `图片附件(多图)`）

示例：

```bash
lark-cli api POST /open-apis/bitable/v1/apps/<app_token>/tables/<table_id>/fields --data '{"field_name":"图片附件(多图)","type":17}'
```

## 6. 执行抓取并同步

使用项目脚本：`scripts/xhs_scrape_cdp.py`

推荐命令：

```bash
python3 scripts/xhs_scrape_cdp.py \
  --url-file <url_list.txt> \
  --sync-feishu-bitable-wiki "<wiki_url>" \
  --bitable-table-id "<table_id>" \
  --bitable-attach-field "图片附件(多图)" \
  --only-image-notes \
  --ua-rotate \
  --risk-circuit-breaker \
  --risk-max-hits 2 \
  --risk-pause-min 180 --risk-pause-max 360
```

说明：

- 脚本会抓取文字与图片 URL。
- `--only-image-notes` 开启后，仅写入有图片的笔记；视频/无图笔记会跳过（标记 `skipped_non_image`）。
- 图片会下载并上传到飞书，再写入 `图片附件(多图)` 同一个单元格。
- 上传临时文件会在上传后立即删除。
- 同步时会按最终 `url` 去重，避免重复写入同一笔记。
- 附件上传单张失败会记录告警并继续，不中断整批任务。

## 7. 输出与校验

完成后至少做一次回读校验：

```bash
lark-cli base +record-list --base-token <app_token> --table-id <table_id>
```

确认：

- 新增记录已写入。
- `图片附件(多图)` 字段存在且有附件 token。
- 若开启 `--only-image-notes`，检查 `skipped_non_image` 数量是否符合预期。

向用户汇报：

- 成功写入条数
- 失败条数及原因
- 跳过条数（如 `skipped_non_image`）
- 是否触发风控熔断

## 8. 失败处理策略

- `lark-cli` 未安装：停止执行，先引导安装。
- 未登录/权限不足：停止执行，引导 `auth login` 后重试。
- wiki 非 bitable：停止执行并要求提供多维表格链接。
- 字段缺失创建失败：汇报具体字段与错误码。
- 小红书风控命中：按脚本熔断逻辑暂停/终止，返回可重试建议。
- 附件上传接口偶发错误（如 5000 / EOF）：不终止整批，记录告警并在结果中说明可能存在少量附件缺失。
