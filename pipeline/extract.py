"""正文与头图提取：trafilatura 全文（Markdown 输出）+ og:image 下载压缩。

失败策略：
- 正文抓不到（反爬/付费墙）→ 回退用 RSS 摘要当正文，页面会标注
- 图片抓不到 → image=None，前端用占位图
"""
import io
import logging
import re

import requests
import trafilatura
from PIL import Image

import config

log = logging.getLogger("pipeline")

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MIN_FULLTEXT_CHARS = 400


def fetch_html(url: str) -> str:
    resp = requests.get(url, timeout=config.HTTP_TIMEOUT,
                        headers={"User-Agent": config.USER_AGENT}, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def extract_fulltext(url: str, snippet: str, item_type: str) -> tuple[str, str]:
    """返回 (markdown 正文, 来源说明 note)。note 用于页面标注正文来源方式。"""
    if item_type == "paper":
        # arXiv 论文：原文即摘要页，用 API 返回的摘要作为正文
        return snippet.strip(), "arxiv_abstract"

    if url.split("/")[2] in config.FULLTEXT_BLOCKLIST:
        return snippet.strip(), "fallback_snippet"

    try:
        html = fetch_html(url)
        text = trafilatura.extract(
            html, output_format="markdown", include_comments=False,
            include_tables=True, include_links=False, favor_recall=True, url=url,
        )
        if text and len(text) >= MIN_FULLTEXT_CHARS:
            return text.strip(), "fulltext"
        log.warning("正文过短(%d 字符)，回退摘要: %s", len(text or ""), url)
    except Exception as e:
        log.warning("正文抓取失败 %s: %s", url, e)
    return snippet.strip(), "fallback_snippet"


def extract_og_image(url: str) -> str | None:
    """从页面 <head> 提取 og:image / twitter:image，返回绝对 URL。"""
    try:
        html = fetch_html(url)
        m = (re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html)
             or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
             or re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)', html))
        if not m:
            return None
        img_url = m.group(1).replace("&amp;", "&")
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        elif img_url.startswith("/"):
            from urllib.parse import urlparse
            p = urlparse(url)
            img_url = f"{p.scheme}://{p.netloc}{img_url}"
        return img_url if img_url.startswith("http") else None
    except Exception as e:
        log.warning("头图提取失败 %s: %s", url, e)
        return None


def download_image(img_url: str, save_path) -> str | None:
    """下载 og:image，最长边压到 1280px，JPEG q80，返回相对路径；任何失败返回 None。"""
    try:
        resp = requests.get(img_url, timeout=config.HTTP_TIMEOUT,
                            headers={"User-Agent": config.USER_AGENT}, stream=True, allow_redirects=True)
        resp.raise_for_status()
        buf = io.BytesIO()
        for chunk in resp.iter_content(64 * 1024):
            buf.write(chunk)
            if buf.tell() > MAX_IMAGE_BYTES:
                raise ValueError("image too large")
        buf.seek(0)

        img = Image.open(buf)
        img = img.convert("RGB")
        img.thumbnail((1280, 1280), Image.LANCZOS)
        img.save(save_path, "JPEG", quality=80, progressive=True, optimize=True)
        return str(save_path.name)
    except Exception as e:
        log.warning("图片下载/压缩失败 %s: %s", img_url, e)
        return None
