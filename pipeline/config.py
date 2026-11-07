"""全局配置：全部通过环境变量 / 常量集中管理，凭据绝不写入文件。"""
import os
from pathlib import Path

# ---------- 路径 ----------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
ARTICLES_DIR = DATA_DIR / "articles"
IMAGES_DIR = DATA_DIR / "images"
INDEX_FILE = DATA_DIR / "index.json"
FAILED_FILE = DATA_DIR / "failed.json"  # 记录失败文章的重试次数，超过上限放弃

# ---------- LLM（DeepSeek，OpenAI 兼容接口，可换家） ----------
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
LLM_TIMEOUT = 180          # 单次调用超时（秒）
LLM_MAX_RETRIES = 4        # 单次调用重试次数

# ---------- 采集 ----------
MAX_PER_DAY = int(os.environ.get("MAX_ARTICLES", "9"))   # 每日精选上限（5~10）
FETCH_WINDOW_HOURS = 48    # 只考虑最近 N 小时内发布的条目
CANDIDATE_LIMIT = 24       # 送入 LLM 精筛的候选上限
MAX_FAILED_ATTEMPTS = 2    # 同一 URL 失败 N 次后放弃
HTTP_TIMEOUT = 25          # 抓网页超时（秒）
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 AiInsightBot/1.0"
)

# ---------- 概括 / 翻译 ----------
SUMMARY_INPUT_LIMIT = 14000   # 送入概括的正文长度上限（字符）
TRANSLATE_CHUNK_SIZE = 3200   # 全文翻译分块大小（字符）

# 禁止抓正文的域名（反爬严厉 / 条款不允许的站点，只显示 RSS 摘要）
FULLTEXT_BLOCKLIST = set()

for _d in (ARTICLES_DIR, IMAGES_DIR):
    _d.mkdir(parents=True, exist_ok=True)
