# Quickstart

```bash
cd /Users/sinman/Projects/Other/xhs-test
python3 skill-xhs-feishu-sync/scripts/xhs_scrape_cdp.py \
  --url-file output/xhs/urls.txt \
  --sync-feishu-bitable-wiki "https://exmuxuzlt5b.feishu.cn/wiki/WYk2wK9ixij5pmk9OXacF9TVnqd?table=tblv7cTmxi4eJ7lw&view=vewr7OIQXj" \
  --bitable-table-id "tblv7cTmxi4eJ7lw" \
  --bitable-attach-field "图片附件(多图)" \
  --ua-rotate \
  --risk-circuit-breaker
```
