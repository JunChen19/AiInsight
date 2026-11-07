"""DeepSeek（OpenAI 兼容）适配器 + 三个 AI 任务：批量精筛 / 双语概括 / 全文翻译。

换家只改环境变量 DEEPSEEK_BASE_URL / DEEPSEEK_MODEL，不改代码。
"""
import json
import logging
import random
import time
from urllib.parse import urlparse

import requests

import config

log = logging.getLogger("pipeline")


class LLMError(Exception):
    pass


def _chat(messages: list[dict], json_mode: bool = False, max_tokens: int = 8000) -> str:
    """单次对话调用，带重试退避。"""
    if not config.DEEPSEEK_API_KEY:
        raise LLMError("缺少 DEEPSEEK_API_KEY 环境变量")

    body = {
        "model": config.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    url = config.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    last_err = None
    for attempt in range(1, config.LLM_MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=config.LLM_TIMEOUT)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                raise RuntimeError(last_err)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            # 思考型模型可能带 reasoning 字段，content 即最终答案
            return content.strip()
        except Exception as e:
            last_err = str(e)
            if attempt < config.LLM_MAX_RETRIES:
                wait = 2 ** attempt + random.uniform(0, 1.5)
                log.warning("LLM 调用失败(第%d次)：%s，%.1fs 后重试", attempt, last_err, wait)
                time.sleep(wait)
    raise LLMError(f"LLM 调用最终失败: {last_err}")


def _parse_json(text: str) -> dict | list:
    """解析模型返回的 JSON（容忍 markdown 代码块包裹）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


# ---------------- 1. 批量精筛 ----------------
CATEGORIES = ["model-release", "rl", "technique", "performance", "other"]

CURATE_SYSTEM = """你是 AI 领域的资深新闻编辑，为"AI Insight"资讯站筛选每日新闻。读者关注：
1. 模型发布（新模型/新版本/开源权重发布，功能与规格）
2. 模型新技术（训练方法、架构创新、后训练技术）
3. 【最高优先】强化学习相关：RLHF、奖励建模、GRPO/PPO 等训练算法、agentic RL、self-play、RL 新应用（机器人/推理/代码等）
4. 性能与精度：benchmark 评测、SOTA、量化/推理加速、精度提升

筛选规则：
- 保留：模型技术相关，以上面 1-4 判断；强化学习相关大幅加分
- 排除：融资/股价/人事/政策法规/诉讼等商业新闻、纯营销软文、与 AI 模型技术无关的新闻
- arXiv 论文门槛更高：只保留有明确创新点或来自知名机构的高信号论文（score>=6），日常灌水论文不要
- score 为新闻价值 0-10

输入 JSON 数组，每项 {id, source, title, snippet}。严格返回 json：
{"results": [{"id": "...", "keep": true/false, "score": 0-10, "category": "model-release|rl|technique|performance|other", "reason": "一句话中文理由"}]}"""


def curate(candidates: list[dict]) -> list[dict]:
    """LLM 批量精筛，返回按分数降序的入选列表（附 category/reason）。"""
    kept: list[dict] = []
    batch_size = 12
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        payload = [{"id": c.get("cid"), "source": c["source_name"], "title": c["title"],
                    "snippet": c["snippet"][:400]} for c in batch]
        try:
            out = _chat(
                [{"role": "system", "content": CURATE_SYSTEM},
                 {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                json_mode=True, max_tokens=4000,
            )
            results = _parse_json(out).get("results", [])
        except Exception as e:
            log.error("精筛批次失败，跳过 %d 条: %s", len(batch), e)
            continue

        by_id = {r.get("id"): r for r in results if isinstance(r, dict)}
        for c in batch:
            r = by_id.get(c.get("cid"))
            if not r or not r.get("keep"):
                continue
            c["llm_score"] = int(r.get("score") or 0)
            cat = r.get("category", "other")
            c["category"] = cat if cat in CATEGORIES else "other"
            c["reason"] = str(r.get("reason", ""))[:200]
            kept.append(c)
        time.sleep(1)

    kept.sort(key=lambda x: (x.get("llm_score", 0), x.get("score", 0)), reverse=True)
    log.info("LLM 精筛：%d 候选 → %d 入选", len(candidates), len(kept))
    return kept


# ---------------- 2. 双语概括 ----------------
SUMMARIZE_SYSTEM = """你是 AI 领域资深编辑。基于给定英文文章内容，严格返回 json：
{
  "title_zh": "中文标题（简洁专业，模型名/产品名/专有名词保留英文）",
  "summary_en": "English summary in 3-5 sentences. Keep key technical details: what was released/invented, how it works, concrete performance/precision numbers if any.",
  "summary_zh": "对应的中文概括（3-5句，信息与英文版等价，技术术语首次出现可附英文缩写，保留具体数字）",
  "tags": ["2-5个小写英文标签，如 rl, model-release, reward-model, llm, benchmark"]
}"""


def summarize(title: str, text: str) -> dict:
    user = f"文章标题：{title}\n\n文章内容：\n{text[: config.SUMMARY_INPUT_LIMIT]}"
    out = _chat(
        [{"role": "system", "content": SUMMARIZE_SYSTEM},
         {"role": "user", "content": user}],
        json_mode=True, max_tokens=2000,
    )
    data = _parse_json(out)
    return {
        "title_zh": str(data.get("title_zh", "")).strip(),
        "summary_en": str(data.get("summary_en", "")).strip(),
        "summary_zh": str(data.get("summary_zh", "")).strip(),
        "tags": [str(t).lower()[:24] for t in (data.get("tags") or [])][:5],
    }


# ---------------- 3. 全文翻译（分块） ----------------
TRANSLATE_SYSTEM = """将用户给出的英文技术文章片段翻译成简体中文。要求：
- 输入是 Markdown，输出也保持 Markdown：标题层级、列表、粗体、表格结构原样保留
- 代码块内容不翻译
- 模型名、产品名、基准名（如 MMLU、GSM8K）、专有缩写保留英文
- 数字、单位、版本号严格保持原样
- 直接输出译文，不要任何解释或原文"""


def _split_chunks(text: str, size: int) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks, cur = [], ""
    for p in paragraphs:
        while len(p) > size:  # 超长单段硬切
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(p[:size])
            p = p[size:]
        if len(cur) + len(p) + 2 <= size:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def translate(text: str) -> str:
    """全文翻译为中文，分块处理，块间加回车。失败时抛异常由上层决定降级。"""
    text = text.strip()
    if not text:
        return ""
    chunks = _split_chunks(text, config.TRANSLATE_CHUNK_SIZE)
    parts = []
    for i, chunk in enumerate(chunks, 1):
        out = _chat(
            [{"role": "system", "content": TRANSLATE_SYSTEM},
             {"role": "user", "content": chunk}],
            max_tokens=8000,
        )
        # 去掉模型可能加的代码块包裹
        for tag in ("```markdown", "```\n"):
            if out.startswith(tag):
                out = out[len(tag):].rstrip("`").strip()
        parts.append(out.strip())
        log.info("  翻译分块 %d/%d 完成", i, len(chunks))
        time.sleep(0.5)
    return "\n\n".join(parts)
