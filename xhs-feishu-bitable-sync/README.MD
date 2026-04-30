# xhs-feishu-bitable-sync 使用说明

## 1. 项目用途
本项目的核心脚本是：

- `scripts/xhs_scrape_cdp.py`

该脚本用于：

1. 通过 Chrome CDP 抓取小红书笔记数据（标题、正文、tag、作者、发布时间、互动数、图片 URL 等）。
2. 直接同步到飞书：
   - 飞书电子表格（Sheet，旧模式）
   - 飞书多维表格（Bitable/Base，推荐）
3. 在多维表格模式下，支持把图片下载后上传为附件，并写入同一个附件字段（如 `图片附件(多图)`）。

---

## 2. 当前推荐模式
推荐使用 **多维表格直连模式**，特点：

- 不依赖中间 `csv` 文件。
- 抓取结果直接写入 Base。
- 图片可作为附件写入同一个单元格。

> 说明：脚本仍保留 `--save-csv` 选项用于调试或导出，但默认不生成 CSV。

---

## 3. 前置要求

### 3.1 本地环境

- macOS / Linux
- Python 3.10+
- Node.js（用于 web-access 相关脚本）
- Chrome（且开启 remote debugging）
- `lark-cli` 已安装并可用

建议先检查：

```bash
python3 --version
```

若未安装：

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

### 3.2 Chrome CDP 可用

在 Chrome 打开：

- `chrome://inspect/#remote-debugging`

勾选：

- `Allow remote debugging for this browser instance`

然后确保 `web-access` 的 proxy 已就绪：

```bash
export CLAUDE_SKILL_DIR=/Users/sinman/.agents/skills/web-access
node "$CLAUDE_SKILL_DIR/scripts/check-deps.mjs"
```

### 3.3 飞书授权（必须）

先检查 `lark-cli`：

```bash
lark-cli -v
```

若未安装，可参考官方文档：

- https://open.feishu.cn/document/no_class/mcp-archive/feishu-cli-installation-guide.md

分平台安装示例：

- macOS（Homebrew）：

```bash
brew install lark-cli
lark-cli -v
```

- Linux / Windows（npm）：

```bash
npm install -g @larksuiteoapi/lark-cli
lark-cli -v
```

至少需要以下能力对应 scope：

- `wiki:*`（解析 wiki 链接）
- `base:record:*` / `base:field:*`（读写多维表格）
- `drive:file:upload`（上传图片）

如缺 scope，补授权示例：

```bash
lark-cli auth login --scope "drive:file:upload"
```

查看当前授权状态：

```bash
lark-cli auth status
```

---

## 4. 脚本主要参数

脚本：`scripts/xhs_scrape_cdp.py`

### 4.1 输入参数

- `--url`：单个小红书链接。
- `--url-file`：文本文件，每行一个链接（支持批量）。

两者至少传一个。

### 4.2 抓取节流参数（反风控）

- `--delay-min` / `--delay-max`：URL 间随机间隔秒数（默认 8~18）。
- `--settle-min` / `--settle-max`：页面加载后等待秒数（默认 2~5）。
- `--cooldown-every`：每抓 N 条做一次长冷却（默认 5，0 表示关闭）。
- `--cooldown-min` / `--cooldown-max`：长冷却秒数（默认 45~90）。
- `--max-retries`：单条最大重试次数（默认 3）。
- `--retry-backoff-base` / `--retry-backoff-cap`：重试退避参数。
- `--ua-rotate`：启用 UA 轮换（每条 URL 抓取前随机 UA）。
- `--risk-circuit-breaker`：启用风控熔断。
- `--risk-max-hits`：风控命中累计阈值（默认 2，达到后提前结束批次）。
- `--risk-pause-min` / `--risk-pause-max`：命中风控后的暂停区间秒数（默认 120~240）。

### 4.3 飞书同步参数

#### A) 多维表格（推荐）

- `--sync-feishu-bitable-wiki`：绑定 Base 的 wiki 链接。
- `--bitable-table-id`：表 ID（如 `tblv7cTmxi4eJ7lw`）。
- `--bitable-attach-field`：附件字段名（默认 `图片附件(多图)`）。

#### B) 电子表格（兼容旧模式）

- `--sync-feishu-wiki`：绑定 Sheet 的 wiki 链接。

### 4.4 可选输出

- `--save-json`：保存每条抓取 JSON。
- `--save-csv`：保存 `notes.csv/images.csv`（默认关闭）。
- `--out`：输出目录（默认 `output/xhs`）。

---

## 5. URL 文件格式

示例：`output/xhs/urls.txt`

```txt
https://www.xiaohongshu.com/explore/xxxxx?xsec_token=...
https://www.xiaohongshu.com/explore/yyyyy?xsec_token=...
# 井号开头是注释，会被忽略
```

---

## 6. 推荐命令示例

### 6.1 批量抓取并直连写入多维表格（不落 CSV）

```bash
cd /Users/sinman/Projects/Other/xhs-test
python3 scripts/xhs_scrape_cdp.py \
  --url-file output/xhs/urls.txt \
  --sync-feishu-bitable-wiki "https://exmuxuzlt5b.feishu.cn/wiki/WYk2wK9ixij5pmk9OXacF9TVnqd?table=tblv7cTmxi4eJ7lw&view=vewr7OIQXj" \
  --bitable-table-id "tblv7cTmxi4eJ7lw" \
  --bitable-attach-field "图片附件(多图)"
```

### 6.2 单条抓取 + 写入多维表格

```bash
cd /Users/sinman/Projects/Other/xhs-test
python3 scripts/xhs_scrape_cdp.py \
  --url "https://www.xiaohongshu.com/explore/69e306c9000000002302787a?xsec_token=...&xsec_source=pc_feed" \
  --sync-feishu-bitable-wiki "https://exmuxuzlt5b.feishu.cn/wiki/WYk2wK9ixij5pmk9OXacF9TVnqd?table=tblv7cTmxi4eJ7lw&view=vewr7OIQXj" \
  --bitable-table-id "tblv7cTmxi4eJ7lw"
```

### 6.3 更保守的抓取节奏（降低触发风控概率）

```bash
cd /Users/sinman/Projects/Other/xhs-test
python3 scripts/xhs_scrape_cdp.py \
  --url-file output/xhs/urls.txt \
  --sync-feishu-bitable-wiki "https://exmuxuzlt5b.feishu.cn/wiki/WYk2wK9ixij5pmk9OXacF9TVnqd?table=tblv7cTmxi4eJ7lw&view=vewr7OIQXj" \
  --bitable-table-id "tblv7cTmxi4eJ7lw" \
  --delay-min 15 --delay-max 35 \
  --cooldown-every 3 --cooldown-min 90 --cooldown-max 180 \
  --ua-rotate \
  --risk-circuit-breaker \
  --risk-max-hits 2 \
  --risk-pause-min 180 --risk-pause-max 360
```

### 6.4 调试导出（同时保留本地 CSV/JSON）

```bash
cd /Users/sinman/Projects/Other/xhs-test
python3 scripts/xhs_scrape_cdp.py \
  --url-file output/xhs/urls.txt \
  --sync-feishu-bitable-wiki "https://exmuxuzlt5b.feishu.cn/wiki/WYk2wK9ixij5pmk9OXacF9TVnqd?table=tblv7cTmxi4eJ7lw&view=vewr7OIQXj" \
  --bitable-table-id "tblv7cTmxi4eJ7lw" \
  --save-csv --save-json --out output/xhs
```

---

## 7. 字段映射说明（多维表格）

脚本默认按以下字段名写入（请确保表里有这些列，名称一致）：

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
- `图片附件(多图)`（默认附件列，可通过 `--bitable-attach-field` 改名）

> `url` 字段在 Base 中是强类型 Link，脚本已按对象格式写入。

---

## 8. 关于“无临时文件”说明

你提出的目标是正确的，但目前 `lark-cli base +record-upload-attachment` 要求 `--file` 参数必须是本地路径。

因此脚本采用“最短生命周期文件”策略：

1. 从图片 URL 下载到项目内短期临时文件。
2. 立即调用 `+record-upload-attachment` 上传到附件字段。
3. 立即删除临时文件。

这已经避免了 CSV/JSON 中间落地依赖，并把文件驻留时间压到最短。

---

## 9. 常见问题与排查

### 9.1 `CDP Proxy not reachable`

- 先确认 Chrome remote debugging 已开启。
- 运行：

```bash
export CLAUDE_SKILL_DIR=/Users/sinman/.agents/skills/web-access
node "$CLAUDE_SKILL_DIR/scripts/check-deps.mjs"
```

### 9.2 `missing required scope: drive:file:upload`

- 重新授权：

```bash
lark-cli auth login --scope "drive:file:upload"
```

### 9.3 `URLFieldConvFail`

- 说明 Base 的 `url` 字段写入格式不对。应使用对象格式（脚本已处理）。

### 9.4 `The attachment does not belong to this bitable`

- 说明把 Drive 文件 token 当成 Base 附件直接写入了。
- 必须用 `base +record-upload-attachment` 向目标记录的附件字段上传。

### 9.5 `unsafe file path`

- `lark-cli` 要求上传文件路径为当前目录下相对路径。
- 脚本已处理为项目内临时相对路径。

---

## 10. 安全与风控注意事项

- 小红书对自动化访问有风控，存在账号风险。
- 不建议高并发或短时间密集抓取。
- 建议使用更保守节流参数（见 6.3）。
- 仅抓取你有权限访问且合规的数据。
- 启用 `--ua-rotate` 可以减少单一指纹重复请求。
- 启用 `--risk-circuit-breaker` 可在触发风控信号时自动暂停/熔断批次，避免继续高频请求。

---

## 11. 你可以怎样继续

- 如果你准备长期跑，建议把 URL 清单持续维护在 `output/xhs/urls.txt`。
- 如果你要按天/按批次运行，可以在 Base 中新增批次字段（如 `任务批次`），脚本可按参数自动写入。
- 如果你要做去重（按 `url` 防重复入库），可以在脚本中加“写入前查询”的逻辑。
