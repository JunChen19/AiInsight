"""新闻源采集：官方博客 RSS + 科技媒体 RSS + arXiv（强化学习过滤）。

设计原则：
- 每个源独立 try/except，单个源挂了不影响整体
- 官方实验室博客（tier=official）的条目几乎必然相关，直接进入候选
- arXiv 只取最近提交的强化学习相关论文摘要
"""
import logging
import time
from datetime import datetime, timedelta, timezone

import feedparser
import requests

import config
from common import normalize_url, strip_html, title_similarity

log = logging.getLogger("pipeline")

# tier=official：AI 实验室官方博客，条目默认相关（仍会送 LLM 分类）
# 注：Anthropic 与 DeepLearning.AI(The Batch) 已下线 RSS（2026-11 验证 404），
#     其重要发布由 The Verge / MIT TR / MarkTechPost / Simon Willison 等媒体源覆盖
SOURCES = [
    {"name": "OpenAI",          "url": "https://openai.com/news/rss.xml",                        "tier": "official"},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml",                   "tier": "official"},
    {"name": "Hugging Face",    "url": "https://huggingface.co/blog/feed.xml",                   "tier": "official"},
    {"name": "Google Research", "url": "https://research.google/blog/rss/",                      "tier": "official"},
    {"name": "Meta Newsroom",   "url": "https://about.fb.com/news/feed/",                        "tier": "media"},
    {"name": "MarkTechPost",    "url": "https://www.marktechpost.com/feed/",                     "tier": "media"},
    {"name": "VentureBeat AI",  "url": "https://venturebeat.com/category/ai/feed/",              "tier": "media"},
    {"name": "The Verge AI",    "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "tier": "media"},
    {"name": "MIT Tech Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/", "tier": "media"},
    {"name": "Simon Willison",  "url": "https://simonwillison.net/atom/everything/",             "tier": "media"},
]

ARXIV_QUERY = (
    'https://export.arxiv.org/api/query?search_query='
    '%28cat:cs.LG+OR+cat:cs.AI%29+AND+%28ti:%22reinforcement+learning%22+OR+abs:%22reinforcement+learning%22%29'
    '&sortBy=submittedDate&sortOrder=descending'
)


def _get(url: str) -> requests.Response:
    return requests.get(url, timeout=config.HTTP_TIMEOUT,
                        headers={"User-Agent": config.USER_AGENT}, allow_redirects=True)


def _entry_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        st = getattr(entry, attr, None)
        if st:
            return datetime(*st[:6], tzinfo=timezone.utc)
    return None


def _in_window(pub: datetime | None, cutoff: datetime, upper: datetime | None) -> bool:
    """cutoff: 下限（更早的丢弃）；upper: 上限（更新的丢弃，回填用）。无日期视为在窗口内。"""
    if pub and pub < cutoff:
        return False
    if upper and pub and pub > upper:
        return False
    return True


def _fetch_feed(source: dict, cutoff: datetime, upper: datetime | None) -> list[dict]:
    """抓单个 RSS/Atom 源，返回窗口内的候选条目。"""
    try:
        resp = _get(source["url"])
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        log.warning("源抓取失败 %s: %s", source["name"], e)
        return []

    items = []
    for entry in feed.entries:
        link = getattr(entry, "link", "") or ""
        title = getattr(entry, "title", "") or ""
        if not link or not title:
            continue
        pub = _entry_date(entry)
        if not _in_window(pub, cutoff, upper):
            continue  # 超出时间窗口
        items.append({
            "url": link,
            "norm_url": normalize_url(link),
            "title": title.strip(),
            "snippet": strip_html(getattr(entry, "summary", ""))[:1200],
            "source_name": source["name"],
            "tier": source["tier"],
            "published": pub.strftime("%Y-%m-%dT%H:%M:%SZ") if pub else None,
            "type": "blog",
        })
    log.info("源 %-28s %d 条", source["name"], len(items))
    return items


def _fetch_arxiv(cutoff: datetime, upper: datetime | None) -> list[dict]:
    """arXiv API：最近提交的强化学习论文（cs.LG / cs.AI）。"""
    try:
        resp = _get(f"{ARXIV_QUERY}&max_results={config.ARXIV_MAX}")
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        log.warning("arXiv 抓取失败: %s", e)
        return []

    items = []
    for entry in feed.entries:
        pub = _entry_date(entry)
        if not _in_window(pub, cutoff, upper):
            continue
        items.append({
            "url": getattr(entry, "link", ""),
            "norm_url": normalize_url(getattr(entry, "link", "")),
            "title": (getattr(entry, "title", "") or "").strip().replace("\n", " "),
            "snippet": strip_html(getattr(entry, "summary", ""))[:1500],
            "source_name": "arXiv",
            "tier": "paper",
            "published": pub.strftime("%Y-%m-%dT%H:%M:%SZ") if pub else None,
            "type": "paper",
        })
    log.info("源 %-28s %d 条", "arXiv (RL)", len(items))
    return items


# ---------------- 关键词初筛 ----------------
RL_TERMS = [
    "reinforcement learning", "rlhf", "grpo", "ppo", "reward model", "reward modeling",
    "policy gradient", "policy optimization", "q-learning", "actor-critic", "offline rl",
    "multi-agent rl", "rlvr", "agentic rl", "self-play", "curriculum learning",
]
RELEASE_TERMS = [
    "release", "releases", "launch", "launches", "announc", "introduc", "unveil",
    "new model", "open weights", "open-weight", "open-source model", "frontier model", "weights",
]
TECH_TERMS = [
    "architecture", "attention", "transformer", "diffusion model", "distillation", "fine-tun",
    "post-training", "pretraining", "scaling law", "mixture-of-experts", "mixture of experts",
    "long context", "reasoning", "chain-of-thought", "test-time", "inference", "quantization",
    "speculative decoding", "kv cache", "world model", "vision-language", "multimodal",
]
PERF_TERMS = [
    "benchmark", "sota", "state-of-the-art", "accuracy", "flops", "throughput", "latency",
    "fp8", "int4", "int8", "mmlu", "gsm8k", "humaneval", "eval", "evaluation", "performance",
]
NEG_TERMS = [
    "funding", "raises $", "series a", "series b", "series c", "ipo", "layoff", "layoffs",
    "lawsuit", "regulation", "regulator", "ban ", "bans ", "stock", "acquisition", "acquires",
    "hiring", "resign", "scandal", "donate", "donation",
]


def keyword_score(item: dict) -> int:
    text = (item["title"] + " \n " + item["snippet"]).lower()
    score = 0
    score += 3 * sum(t in text for t in RL_TERMS)
    score += 3 * sum(t in text for t in RELEASE_TERMS)
    score += 2 * sum(t in text for t in TECH_TERMS)
    score += 2 * sum(t in text for t in PERF_TERMS)
    score -= 5 * sum(t in text for t in NEG_TERMS)
    if item["tier"] == "official":
        score += 2  # 官方博客默认加分
    if item["tier"] == "paper":
        score += 2  # arXiv RL 论文已经过主题过滤
    return score


def gather_candidates(seen_norm_urls: set, seen_titles: list[str]) -> list[dict]:
    """抓全部源 → 时间窗口过滤 → URL/标题去重 → 关键词打分排序，返回候选列表。"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.FETCH_WINDOW_HOURS)
    upper = (datetime.now(timezone.utc) - timedelta(hours=config.FETCH_UNTIL_HOURS)
             if config.FETCH_UNTIL_HOURS > 0 else None)

    all_items: list[dict] = []
    for source in SOURCES:
        all_items.extend(_fetch_feed(source, cutoff, upper))
        time.sleep(0.5)  # 礼貌间隔
    all_items.extend(_fetch_arxiv(cutoff, upper))

    # URL 去重（含历史）；同批同 URL 保留先出现者（源列表按优先级排序）
    uniq: list[dict] = []
    batch_urls: set = set()
    for it in all_items:
        if not it["norm_url"] or it["norm_url"] in seen_norm_urls or it["norm_url"] in batch_urls:
            continue
        # 标题去重：同一新闻被多个源报道（与历史 & 本批）
        if any(title_similarity(it["title"], t) >= 0.75 for t in seen_titles):
            continue
        if any(title_similarity(it["title"], u["title"]) >= 0.75 for u in uniq):
            continue
        batch_urls.add(it["norm_url"])
        uniq.append(it)

    scored = []
    for it in uniq:
        it["score"] = keyword_score(it)
        if it["score"] >= 3 or it["tier"] == "official":
            scored.append(it)
    scored.sort(key=lambda x: x["score"], reverse=True)
    log.info("候选：抓到 %d → 去重后 %d → 初筛后 %d", len(all_items), len(uniq), len(scored))
    return scored[: config.CANDIDATE_LIMIT]
