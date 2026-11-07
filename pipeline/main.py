"""AiInsight 每日采集主流程。

运行方式：DEEPSEEK_API_KEY=xxx python main.py
流程：抓源 → 初筛去重 → LLM 精筛 → 全文/头图 → 双语概括 → 全文翻译 → 写入 data/
"""
import logging
import sys
from datetime import datetime, timezone

import config
import extract
import llm
from common import hash8, load_json, now_utc, save_json, slugify
from sources import gather_candidates

log = logging.getLogger("pipeline")


def _parse_ts(ts: str | None) -> datetime:
    if not ts:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    if not config.DEEPSEEK_API_KEY:
        log.error("缺少 DEEPSEEK_API_KEY 环境变量，退出")
        return 1

    index = load_json(config.INDEX_FILE, [])
    failed = load_json(config.FAILED_FILE, {})

    seen_urls = {e.get("norm_url") for e in index if e.get("norm_url")}
    seen_urls |= {u for u, n in failed.items() if n >= config.MAX_FAILED_ATTEMPTS}
    seen_titles = [e.get("title_en", "") for e in index]

    candidates = gather_candidates(seen_urls, seen_titles)
    if not candidates:
        log.info("本次没有新候选，结束")
        return 0

    for c in candidates:
        c["cid"] = hash8(c["norm_url"])

    kept = llm.curate(candidates)[: config.MAX_PER_DAY]
    if not kept:
        log.info("LLM 精筛后无入选文章，结束")
        return 0
    log.info("本日入选 %d 篇：%s", len(kept), " | ".join(k["title"][:40] for k in kept))

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    new_entries = []

    for item in kept:
        norm = item["norm_url"]
        aid = f"{today}-{slugify(item['title'], 40)}-{hash8(norm)[:6]}"
        try:
            # 1) 全文
            content_en, note = extract.extract_fulltext(item["url"], item["snippet"], item["type"])

            # 2) 头图（arXiv 论文没有头图，跳过）
            image = None
            if item["type"] != "paper":
                og = extract.extract_og_image(item["url"])
                if og:
                    saved = extract.download_image(og, config.IMAGES_DIR / f"{aid}.jpg")
                    if saved:
                        image = f"images/{saved}"

            # 3) 双语概括（失败则本篇放弃，下次运行重试）
            try:
                s = llm.summarize(item["title"], content_en)
            except llm.LLMError as e:
                raise RuntimeError(f"概括失败: {e}")
            if not s["summary_en"]:
                raise RuntimeError("概括结果为空")

            # 4) 全文翻译（失败不阻塞：中文版标记暂缺）
            content_zh, translation_failed = "", False
            try:
                content_zh = llm.translate(content_en)
            except llm.LLMError as e:
                log.warning("翻译失败（本篇中文全文暂缺）：%s", e)
                translation_failed = True

            fetched = now_utc()
            article = {
                "id": aid,
                "url": item["url"],
                "title_en": item["title"],
                "title_zh": s["title_zh"] or item["title"],
                "source_name": item["source_name"],
                "source_url": item["url"],
                "published": item.get("published"),
                "fetched_at": fetched,
                "type": item["type"],
                "category": item["category"],
                "tags": s["tags"],
                "image": image,
                "summary_en": s["summary_en"],
                "summary_zh": s["summary_zh"] or s["summary_en"],
                "content_en": content_en,
                "content_zh": content_zh,
                "content_note": note,                 # fulltext / fallback_snippet / arxiv_abstract
                "translation_failed": translation_failed,
            }
            save_json(config.ARTICLES_DIR / f"{aid}.json", article)

            entry = {k: article[k] for k in (
                "id", "url", "title_en", "title_zh", "source_name", "published",
                "fetched_at", "type", "category", "tags", "image",
                "summary_en", "summary_zh")}
            entry["norm_url"] = norm
            new_entries.append(entry)
            failed.pop(norm, None)
            log.info("✔ 完成 [%s] %s", item["category"], item["title"][:60])

        except Exception as e:
            failed[norm] = failed.get(norm, 0) + 1
            log.error("✘ 处理失败(%d/%d) %s：%s", failed[norm],
                      config.MAX_FAILED_ATTEMPTS, item["title"][:60], e)

    if new_entries:
        index = sorted(new_entries + index, key=lambda e: _parse_ts(e.get("published") or e.get("fetched_at")), reverse=True)
        save_json(config.INDEX_FILE, index)
    save_json(config.FAILED_FILE, failed)

    log.info("本次运行结束：成功 %d 篇，失败 %d 篇", len(new_entries), len(kept) - len(new_entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
