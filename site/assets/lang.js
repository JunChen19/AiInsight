/* 共享：多语言字典 + 全局语言开关（localStorage 记忆） */
(function () {
  "use strict";

  const DICT = {
    zh: {
      tagline: "每日 AI 前沿情报 · 重点关注强化学习",
      latest: "最近更新",
      catAll: "全部", catModelRelease: "模型发布", catRL: "强化学习",
      catTechnique: "新技术", catPerformance: "性能评测", catOther: "其他",
      searchPh: "搜索标题 / 摘要 / 标签…",
      entryUnit: "篇",
      emptyTitle: "这里还没有内容",
      emptyBody: "每日北京时间早晨自动抓取。如果今天是第一次运行，请先触发一次 GitHub Actions 工作流。",
      errTitle: "内容加载失败",
      errBody: "请检查网络后重试，或直接访问 GitHub 仓库的数据目录。",
      retry: "重试",
      paper: "论文",
      noImage: "无头图",
      summaryLabel: "概括",
      contentLabel: "原文",
      backHome: "← 返回列表",
      viewOrigin: "查看原文 ↗",
      translationMissing: "本篇中文翻译暂缺（生成时翻译服务异常），展示英文原文。",
      contentFromFeed: "原文站点限制抓取，以下为 RSS 摘要。",
      contentFromArxiv: "arXiv 论文：以下为作者摘要。",
      machineTranslated: "中文版由 DeepSeek 自动翻译，仅供参考",
      articleNotFound: "文章不存在",
      articleNotFoundBody: "链接可能已失效，请返回列表查看最新内容。",
      footerSources: "数据来源：OpenAI / Google DeepMind / Hugging Face / Meta / arXiv / The Verge / MIT Technology Review / MarkTechPost / VentureBeat / Simon Willison 等",
      footerPowered: "由 GitHub Actions 每日自动抓取更新 · 概括与翻译：DeepSeek",
      footerCopyright: "文章版权归原作者所有，本站仅作学习研究之用，转载请访问原文链接",
      weekdays: ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"],
      dateFmt: (y, m, d) => `${m}月${d}日`,
      timeFmt: (hh, mm) => `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`,
    },
    en: {
      tagline: "Daily AI intelligence · with a focus on reinforcement learning",
      latest: "Updated",
      catAll: "All", catModelRelease: "Model release", catRL: "Reinforcement learning",
      catTechnique: "Techniques", catPerformance: "Performance", catOther: "Other",
      searchPh: "Search titles, summaries, tags…",
      entryUnit: "items",
      emptyTitle: "Nothing here yet",
      emptyBody: "The pipeline runs every morning (Beijing time). If this is the first run, trigger the GitHub Actions workflow once.",
      errTitle: "Failed to load content",
      errBody: "Check your connection and retry, or browse the data directory in the GitHub repo.",
      retry: "Retry",
      paper: "Paper",
      noImage: "No image",
      summaryLabel: "Summary",
      contentLabel: "Original article",
      backHome: "← Back to list",
      viewOrigin: "View original ↗",
      translationMissing: "Chinese translation unavailable (translation failed at build time); showing the English original.",
      contentFromFeed: "The source site blocks full-text scraping; showing the RSS summary.",
      contentFromArxiv: "arXiv paper: author abstract shown below.",
      machineTranslated: "Chinese version auto-translated by DeepSeek",
      articleNotFound: "Article not found",
      articleNotFoundBody: "The link may be stale. Head back to the list for the latest.",
      footerSources: "Sources: OpenAI / Google DeepMind / Hugging Face / Meta / arXiv / The Verge / MIT Technology Review / MarkTechPost / VentureBeat / Simon Willison",
      footerPowered: "Auto-updated daily by GitHub Actions · Summaries & translation: DeepSeek",
      footerCopyright: "Copyright belongs to the original authors. For study purposes — see original articles.",
      weekdays: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
      dateFmt: (y, m, d) => ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1] + " " + d,
      timeFmt: (hh, mm) => `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`,
    },
  };

  const CAT_KEYS = {
    "model-release": "catModelRelease",
    rl: "catRL",
    technique: "catTechnique",
    performance: "catPerformance",
    other: "catOther",
  };

  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* 隐私模式等场景忽略 */ } }

  let lang = lsGet("aii-lang") || "zh";

  function applyLang() {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-lang-switch] button").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.lang === lang));
    });
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = DICT[lang][el.dataset.i18n] || "";
    });
    document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
      el.placeholder = DICT[lang][el.dataset.i18nPh] || "";
    });
    document.dispatchEvent(new CustomEvent("aii:langchange", { detail: { lang } }));
  }

  window.AII = {
    get lang() { return lang; },
    t(key) { return DICT[lang][key]; },
    catLabel(cat) { return DICT[lang][CAT_KEYS[cat] || "catOther"]; },
    titleOf(a) { return (lang === "zh" ? a.title_zh : a.title_en) || a.title_en || a.title_zh; },
    summaryOf(a) { return (lang === "zh" ? a.summary_zh : a.summary_en) || a.summary_en || a.summary_zh; },
    setLang(l) {
      lang = l;
      lsSet("aii-lang", l);
      applyLang();
    },
    applyLang,
    // 相对路径取数据（站点挂在 /AiInsight/ 子路径下）
    dataUrl(path) {
      const root = document.documentElement.dataset.dataRoot || "../data/";
      return root + path;
    },
  };

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-lang-switch] button");
    if (btn) window.AII.setLang(btn.dataset.lang);
  });

  document.addEventListener("DOMContentLoaded", applyLang);
})();
