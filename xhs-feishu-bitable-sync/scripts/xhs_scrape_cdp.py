import argparse
import json
import os
import random
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple

CDP_BASE = "http://localhost:3456"

DEFAULT_UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

RISK_KEYWORDS = [
    "访问异常", "异常请求", "验证", "captcha", "人机验证", "登录后", "登录查看更多", "频繁", "稍后再试", "not available",
]

BJ_TZ = timezone(timedelta(hours=8))


def now_beijing_str() -> str:
    return datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")

EXTRACT_JS = r"""(() => {
  const nowIso = new Date().toISOString();
  const text = (el) => (el && el.textContent ? el.textContent.trim() : "");
  const firstText = (selectors) => {
    for (const sel of selectors) {
      const t = text(document.querySelector(sel));
      if (t) return t;
    }
    return "";
  };
  const uniq = (arr) => {
    const out = [];
    const seen = new Set();
    for (const x of arr || []) {
      const v = (x || "").trim();
      if (!v || seen.has(v)) continue;
      seen.add(v);
      out.push(v);
    }
    return out;
  };

  const title = firstText([".title", "h1", "[data-testid='note-title']"]) || (document.title || "");
  const author = firstText([".author-container .username", ".author .name", "[data-testid='author-name']"]);
  const publishTime = firstText([".date", "time", "[class*='date']", "[class*='time']"]);
  const rawContent = firstText([".desc", "[data-testid='note-content']", ".note-content", "article"]);

  const tags = uniq((rawContent.match(/#[^\s#]+/g) || []).map(t => t.trim()));
  const content = rawContent.replace(/#[^\s#]+/g, "").replace(/[ \t]+\n/g, "\n").trim();

  const sliderImages = Array.from(document.querySelectorAll(".note-slider-img img"))
    .map(img => (img.currentSrc || img.src || "").trim())
    .filter(u => u && !u.startsWith("data:"));
  const imgUrls = uniq(sliderImages);

  const countText = (sel) => text(document.querySelector(sel));
  const likeCount = countText(".interact-container .left .like-wrapper .count");
  const collectCount = countText(".interact-container .left .collect-wrapper .count");
  const commentCount = countText(".interact-container .left .chat-wrapper .count");
  const shareCount = countText(".interact-container .share-wrapper .count");

  const mediaText = text(document.querySelector(".media-container"));
  const m = mediaText.match(/(\d+)\s*\/\s*(\d+)/);
  const pagerTotal = (m && m[2]) ? m[2] : "";

  return {
    url: location.href,
    fetchedAt: nowIso,
    title,
    author,
    publishTime,
    content,
    tags,
    images: imgUrls,
    counts: { like: likeCount, collect: collectCount, comment: commentCount, share: shareCount },
    debug: { documentTitle: document.title || "", mediaText, pagerTotal, sliderImageCount: imgUrls.length }
  };
})()"""


def http_get(url: str, timeout: float = 30.0):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype or data[:1] in (b"{", b"["):
                return json.loads(data.decode("utf-8", errors="replace"))
            return data.decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise RuntimeError(f"CDP Proxy not reachable: {e}") from e


def http_post(url: str, body: str, timeout: float = 30.0):
    req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return raw


def cdp_new(url: str) -> str:
    q = urllib.parse.urlencode({"url": url})
    res = http_get(f"{CDP_BASE}/new?{q}")
    if isinstance(res, dict) and "targetId" in res:
        return res["targetId"]
    raise RuntimeError(f"unexpected /new response: {res!r}")


def cdp_close(target: str):
    q = urllib.parse.urlencode({"target": target})
    http_get(f"{CDP_BASE}/close?{q}")


def cdp_eval(target: str, js: str):
    q = urllib.parse.urlencode({"target": target})
    return http_post(f"{CDP_BASE}/eval?{q}", js)


def unwrap_eval_result(res: Any) -> Any:
    if isinstance(res, dict):
        if res.get("error"):
            raise RuntimeError(str(res["error"]))
        if "value" in res:
            return res["value"]
    return res


def wait_for_ready(target: str, timeout_s: float):
    end = time.time() + timeout_s
    while time.time() < end:
        v = unwrap_eval_result(cdp_eval(target, "document && document.readyState"))
        if v == "complete":
            return
        time.sleep(0.5)
    raise RuntimeError("page ready timeout")


def rand_sleep(a: float, b: float):
    if b <= 0:
        return
    time.sleep(random.uniform(max(0.0, a), max(a, b)))


def resolve_redirect_url(url: str, timeout: float = 20.0) -> Tuple[str, List[str]]:
    class _RedirectRecorder(urllib.request.HTTPRedirectHandler):
        def __init__(self):
            super().__init__()
            self.chain: List[str] = []

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.chain.append(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    recorder = _RedirectRecorder()
    opener = urllib.request.build_opener(recorder)
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": DEFAULT_UA_POOL[0]})
    with opener.open(req, timeout=timeout) as resp:
        final_url = resp.geturl()
    chain = [url] + recorder.chain
    if chain[-1] != final_url:
        chain.append(final_url)
    return final_url, chain


def load_urls(args) -> List[str]:
    items: List[str] = []
    if args.url:
        items.append(args.url.strip())
    if args.url_file:
        with open(args.url_file, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    items.append(s)
    out, seen = [], set()
    for u in items:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    if not out:
        raise RuntimeError("Provide --url or --url-file with valid URLs")
    return out


def shell_json(cmd: List[str]) -> Dict[str, Any]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    out = p.stdout.strip()
    idx = out.rfind("\n{")
    s = out[idx + 1:] if idx >= 0 else out
    return json.loads(s)


def parse_wiki_to_bitable(wiki_url: str) -> str:
    token = [x for x in urllib.parse.urlparse(wiki_url).path.split("/") if x][1]
    node = shell_json(["lark-cli", "api", "GET", "/open-apis/wiki/v2/spaces/get_node", "--params", json.dumps({"token": token})])
    n = (node.get("data") or {}).get("node") or {}
    if n.get("obj_type") != "bitable":
        raise RuntimeError("wiki is not bitable")
    return n.get("obj_token", "")


def base_next_seq(app_token: str, table_id: str) -> int:
    res = shell_json(["lark-cli", "base", "+record-list", "--base-token", app_token, "--table-id", table_id])
    rows = (res.get("data") or {}).get("data") or []
    max_seq = 0
    for r in rows:
        try:
            v = int(r[0]) if r and r[0] is not None and str(r[0]).strip() else 0
        except Exception:
            v = 0
        if v > max_seq:
            max_seq = v
    return max_seq + 1


def parse_md_link_url(s: str) -> str:
    text = (s or "").strip()
    if "](" in text and text.startswith("[") and text.endswith(")"):
        i = text.rfind("](")
        if i >= 0:
            return text[i + 2:-1].strip()
    return text


def base_existing_urls(app_token: str, table_id: str) -> set:
    res = shell_json(["lark-cli", "base", "+record-list", "--base-token", app_token, "--table-id", table_id])
    fields = (res.get("data") or {}).get("fields") or []
    rows = (res.get("data") or {}).get("data") or []
    if "url" not in fields:
        return set()
    idx = fields.index("url")
    out = set()
    for r in rows:
        if not isinstance(r, list) or idx >= len(r):
            continue
        v = r[idx]
        if not v:
            continue
        out.add(parse_md_link_url(str(v)))
    return out


def base_create_record(app_token: str, table_id: str, fields: Dict[str, Any]) -> str:
    res = shell_json(["lark-cli", "api", "POST", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records", "--data", json.dumps({"fields": fields}, ensure_ascii=False)])
    rid = (((res.get("data") or {}).get("record") or {}).get("record_id")) or ""
    if not rid:
        raise RuntimeError("create record failed")
    return rid


def base_upload_attachment_from_url(app_token: str, table_id: str, record_id: str, field_name: str, image_url: str, name: str):
    rel_dir = ".xhs_tmp_upload"
    os.makedirs(rel_dir, exist_ok=True)
    rel_path = os.path.join(rel_dir, f"{int(time.time()*1000)}_{random.randint(1000,9999)}.webp")
    try:
        with urllib.request.urlopen(image_url, timeout=60) as resp, open(rel_path, "wb") as f:
            f.write(resp.read())
        shell_json([
            "lark-cli", "base", "+record-upload-attachment",
            "--base-token", app_token,
            "--table-id", table_id,
            "--record-id", record_id,
            "--field-id", field_name,
            "--file", rel_path,
            "--name", name,
        ])
    finally:
        try:
            os.remove(rel_path)
        except FileNotFoundError:
            pass


def apply_ua(target: str, ua: str):
    js = f"(() => {{ Object.defineProperty(navigator, 'userAgent', {{get: () => {json.dumps(ua)}}}); return navigator.userAgent; }})()"
    try:
        unwrap_eval_result(cdp_eval(target, js))
    except Exception:
        pass


def detect_risk_page(target: str, keywords: List[str]) -> str:
    text = unwrap_eval_result(cdp_eval(target, "(document.title||'') + '\\n' + ((document.body&&document.body.innerText)||'')"))
    s = str(text).lower()
    for k in keywords:
        if k.lower() in s:
            return k
    return ""


def scrape_one(url: str, args, index: int, total: int, ua_pool: List[str]) -> Dict[str, Any]:
    last_err = None
    resolved_url = url
    redirect_chain = [url]
    try:
        resolved_url, redirect_chain = resolve_redirect_url(url, timeout=min(20.0, args.timeout))
    except Exception:
        resolved_url = url
        redirect_chain = [url]
    for attempt in range(1, args.max_retries + 1):
        target = None
        try:
            target = cdp_new(resolved_url)
            if ua_pool:
                apply_ua(target, random.choice(ua_pool))
            wait_for_ready(target, args.timeout)
            rand_sleep(args.settle_min, args.settle_max)

            hit = detect_risk_page(target, RISK_KEYWORDS)
            if hit:
                raise RuntimeError(f"risk_page_detected:{hit}")

            data = unwrap_eval_result(cdp_eval(target, EXTRACT_JS))
            if not isinstance(data, dict):
                raise RuntimeError(f"unexpected extract result: {data!r}")
            data.setdefault("url", resolved_url)
            data.setdefault("sourceUrl", url)
            data.setdefault("redirectChain", redirect_chain)
            data.setdefault("fetchedAt", now_beijing_str())
            return data
        except Exception as e:
            last_err = e
            if attempt < args.max_retries:
                backoff = min(args.retry_backoff_cap, args.retry_backoff_base * (2 ** (attempt - 1)))
                rand_sleep(backoff * 0.8, backoff * 1.2)
        finally:
            if target:
                try:
                    cdp_close(target)
                except Exception:
                    pass
    raise RuntimeError(f"[{index}/{total}] failed for {url} (resolved: {resolved_url}): {last_err}")


def sync_notes_to_bitable_direct(notes: List[Dict[str, Any]], wiki_url: str, table_id: str, attach_field_name: str):
    app_token = parse_wiki_to_bitable(wiki_url)
    seq = base_next_seq(app_token, table_id)
    existing_urls = base_existing_urls(app_token, table_id)
    for item in notes:
        if item.get("status") != "ok":
            continue
        item_url = item.get("url", "")
        if item_url in existing_urls:
            continue
        counts = item.get("counts") or {}
        imgs = item.get("images") or []
        dbg = item.get("debug") or {}
        image_count = str(dbg.get("pagerTotal") or len(imgs))
        fields = {
            "url": {"text": item.get("url", ""), "link": item.get("url", "")},
            "标题": item.get("title", ""),
            "正文": item.get("content", ""),
            "tag": ", ".join(item.get("tags") or []),
            "点赞": str(counts.get("like", "")),
            "收藏": str(counts.get("collect", "")),
            "评论": str(counts.get("comment", "")),
            "转发": str(counts.get("share", "")),
            "作者": item.get("author", ""),
            "发布时间": item.get("publishTime", ""),
            "图片数": image_count,
            "图片URL": "\n".join(imgs),
            "获取时间(UTC)": item.get("fetchedAt", ""),
        }
        rid = base_create_record(app_token, table_id, fields)
        existing_urls.add(item_url)
        for i, u in enumerate(imgs, start=1):
            try:
                base_upload_attachment_from_url(app_token, table_id, rid, attach_field_name, u, f"xhs_{seq}_{i}.webp")
            except Exception as e:
                print(f"[warn] attachment upload failed record={rid} image={i}: {e}")
        seq += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--url-file")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--delay-min", type=float, default=8.0)
    ap.add_argument("--delay-max", type=float, default=18.0)
    ap.add_argument("--settle-min", type=float, default=2.0)
    ap.add_argument("--settle-max", type=float, default=5.0)
    ap.add_argument("--cooldown-every", type=int, default=5)
    ap.add_argument("--cooldown-min", type=float, default=45.0)
    ap.add_argument("--cooldown-max", type=float, default=90.0)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--retry-backoff-base", type=float, default=6.0)
    ap.add_argument("--retry-backoff-cap", type=float, default=45.0)
    ap.add_argument("--ua-rotate", action="store_true", help="enable per-url UA rotation")
    ap.add_argument("--risk-circuit-breaker", action="store_true", help="enable risk-page circuit breaker")
    ap.add_argument("--risk-max-hits", type=int, default=2, help="stop batch after N risk page hits")
    ap.add_argument("--risk-pause-min", type=float, default=120.0, help="pause seconds after risk hit")
    ap.add_argument("--risk-pause-max", type=float, default=240.0, help="pause seconds after risk hit")
    ap.add_argument("--sync-feishu-bitable-wiki", default="")
    ap.add_argument("--bitable-table-id", default="")
    ap.add_argument("--bitable-attach-field", default="图片附件(多图)")
    ap.add_argument("--only-image-notes", action="store_true", help="skip notes without images (e.g., video-only)")
    args = ap.parse_args()

    urls = load_urls(args)
    ua_pool = DEFAULT_UA_POOL if args.ua_rotate else []

    results: List[Dict[str, Any]] = []
    risk_hits = 0
    skipped_non_image = 0

    for i, url in enumerate(urls, start=1):
        if i > 1:
            rand_sleep(args.delay_min, args.delay_max)
        try:
            note = scrape_one(url, args, i, len(urls), ua_pool)
            if args.only_image_notes and not (note.get("images") or []):
                results.append({
                    "url": note.get("url", url),
                    "sourceUrl": url,
                    "fetchedAt": note.get("fetchedAt", now_beijing_str()),
                    "title": note.get("title", ""),
                    "author": note.get("author", ""),
                    "publishTime": note.get("publishTime", ""),
                    "content": note.get("content", ""),
                    "tags": note.get("tags", []),
                    "images": [],
                    "counts": note.get("counts", {}),
                    "debug": note.get("debug", {}),
                    "status": "skipped",
                    "error": "non_image_note",
                })
                skipped_non_image += 1
                continue
            note["status"] = "ok"
            note["error"] = ""
            results.append(note)
        except Exception as e:
            msg = str(e)
            results.append({
                "url": url,
                "fetchedAt": now_beijing_str(),
                "title": "", "author": "", "publishTime": "", "content": "", "tags": [], "images": [], "counts": {}, "debug": {},
                "status": "error", "error": msg,
            })
            if args.risk_circuit_breaker and "risk_page_detected:" in msg:
                risk_hits += 1
                rand_sleep(args.risk_pause_min, args.risk_pause_max)
                if risk_hits >= args.risk_max_hits:
                    break

        if args.cooldown_every > 0 and (i % args.cooldown_every == 0) and i < len(urls):
            rand_sleep(args.cooldown_min, args.cooldown_max)

    if args.sync_feishu_bitable_wiki:
        if not args.bitable_table_id:
            raise RuntimeError("--bitable-table-id is required when syncing bitable")
        sync_notes_to_bitable_direct(results, args.sync_feishu_bitable_wiki, args.bitable_table_id, args.bitable_attach_field)

    ok_count = sum(1 for x in results if x.get("status") == "ok")
    err_count = sum(1 for x in results if x.get("status") == "error")
    skip_count = sum(1 for x in results if x.get("status") == "skipped")
    print(json.dumps({
        "total_input": len(urls),
        "ok": ok_count,
        "error": err_count,
        "skipped": skip_count,
        "skipped_non_image": skipped_non_image,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
