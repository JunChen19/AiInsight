"""通用小工具：URL 归一化、标题去重、slug、JSON 读写。"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_url(url: str) -> str:
    """去掉 utm 等跟踪参数、fragment、末尾斜杠，用于去重比较。"""
    try:
        p = urlparse(url.strip())
        qs = [(k, v) for k, v in parse_qsl(p.query)
              if not k.lower().startswith(("utm_", "fbclid", "ref", "source"))]
        path = re.sub(r"/+$", "", p.path or "")
        return urlunparse((p.scheme or "https", p.netloc.lower(), path, "", urlencode(qs), ""))
    except Exception:
        return url.strip().lower()


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def title_similarity(a: str, b: str) -> float:
    """词集 Jaccard 相似度，用于判断同一新闻被多个源报道。"""
    wa, wb = set(norm_title(a).split()), set(norm_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:max_len].rstrip("-") or "article"


def hash8(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").replace("&nbsp;", " ").replace("&amp;", "&").strip()
