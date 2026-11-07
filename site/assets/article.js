/* 详情页：加载单篇文章 → 简报面板（图+双语概括） + 原文（中英切换） */
(function () {
  "use strict";

  const $ = (s) => document.querySelector(s);
  const esc = window.AII_MD.esc;
  const escAttr = (s) => esc(String(s ?? ""));

  let art = null;
  let sumLang = null;    // null = 跟随全局
  let contLang = null;

  function parseDate(ts) {
    if (!ts) return null;
    const d = new Date(ts);
    return isNaN(d) ? null : d;
  }

  function dateLabel(e) {
    const t = window.AII;
    const d = parseDate(e.published || e.fetched_at);
    if (!d) return "";
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    return `${t.t("dateFmt")(d.getFullYear(), d.getMonth() + 1, d.getDate())} ${t.t("timeFmt")(d.getHours(), d.getMinutes())}`;
  }

  function notFound() {
    const t = window.AII;
    document.title = t.t("articleNotFound") + " · AI Insight";
    $("#article").innerHTML = `
      <div class="state-box">
        <div class="big">${esc(t.t("articleNotFound"))}</div>
        <p>${esc(t.t("articleNotFoundBody"))}</p>
        <p><a href="index.html">${esc(t.t("backHome"))}</a></p>
      </div>`;
  }

  function miniSwitch(sel, current, disabledZh) {
    return `
      <div class="mini-switch" role="group" ${sel ? `data-switch="${sel}"` : ""}>
        <button type="button" data-l="zh" aria-pressed="${current === "zh"}" ${disabledZh ? "disabled" : ""}>中</button>
        <button type="button" data-l="en" aria-pressed="${current === "en"}">EN</button>
      </div>`;
  }

  function render() {
    if (!art) return;
    const t = window.AII;
    const g = t.lang;
    const sl = sumLang || g;
    const hasZh = !!art.content_zh;
    const cl = contLang || g;
    const effCl = hasZh ? cl : "en";

    document.title = t.titleOf(art) + " · AI Insight";

    const isRl = art.category === "rl";
    const chipCls = isRl ? "chip is-rl" : (art.category === "model-release" ? "chip is-release" : "chip");
    const altTitle = g === "zh" ? art.title_en : (art.title_zh !== art.title_en ? art.title_zh : "");

    const sum = sl === "zh" ? (art.summary_zh || art.summary_en) : (art.summary_en || art.summary_zh);
    const content = effCl === "zh" ? art.content_zh : art.content_en;

    const note =
      art.translation_failed && !hasZh ? `<p class="content-note">${esc(t.t("translationMissing"))}</p>` :
      art.content_note === "fallback_snippet" ? `<p class="content-note">${esc(t.t("contentFromFeed"))}</p>` :
      art.content_note === "arxiv_abstract" ? `<p class="content-note">${esc(t.t("contentFromArxiv"))}</p>` : "";

    const figure = art.image
      ? `<img src="${escAttr(t.dataUrl(art.image))}" alt="${escAttr(t.titleOf(art))}" loading="lazy">`
      : `<div class="figure-ph"><div><div class="fp-src">${escAttr(art.source_name)}</div><div>${esc(t.t("noImage"))}</div></div></div>`;

    $("#article").innerHTML = `
      <div class="backline">
        <a class="backlink" href="index.html">${esc(t.t("backHome"))}</a>
        <a class="srclink" href="${escAttr(art.url)}" target="_blank" rel="noopener noreferrer">${esc(t.t("viewOrigin"))}</a>
      </div>

      <header class="art-header">
        <div class="art-cats">
          <span class="${chipCls}">${esc(t.catLabel(art.category))}</span>
          ${(art.tags || []).map((x) => `<span class="tag">${escAttr(x)}</span>`).join("")}
        </div>
        <h1 class="art-title">${escAttr(t.titleOf(art))}${altTitle ? `<span class="alt">${escAttr(altTitle)}</span>` : ""}</h1>
        <div class="art-meta">
          <a class="srclink" href="${escAttr(art.source_url || art.url)}" target="_blank" rel="noopener noreferrer">${escAttr(art.source_name)}</a>
          <span>${esc(dateLabel(art))}</span>
        </div>
      </header>

      <section class="brief" aria-label="${esc(t.t("summaryLabel"))}">
        <div class="brief-figure">${figure}</div>
        <div class="brief-body">
          <div class="block-head">
            <span class="block-title">${esc(t.t("summaryLabel"))}</span>
            ${miniSwitch("sum", sl, false)}
          </div>
          <p class="brief-summary">${escAttr(sl === "zh" ? (art.summary_zh || art.summary_en) : (art.summary_en || art.summary_zh))}</p>
        </div>
      </section>

      <section class="content-section" aria-label="${esc(t.t("contentLabel"))}">
        <div class="block-head">
          <span class="block-title">${esc(t.t("contentLabel"))}</span>
          ${miniSwitch("cont", effCl, !hasZh)}
        </div>
        ${note}
        <div class="md-body">${window.AII_MD.render(content)}</div>
        ${effCl === "zh" && hasZh ? `<p class="content-note">${esc(t.t("machineTranslated"))}</p>` : ""}
      </section>`;

    // 局部语言切换
    document.querySelectorAll("[data-switch]").forEach((sw) => {
      sw.addEventListener("click", (e) => {
        const b = e.target.closest("button[data-l]");
        if (!b || b.disabled) return;
        if (sw.dataset.switch === "sum") sumLang = b.dataset.l;
        else contLang = b.dataset.l;
        const y = window.scrollY;
        render();
        window.scrollTo(0, y); // 保持滚动位置
      });
    });
  }

  async function boot() {
    const id = new URLSearchParams(location.search).get("id");
    if (!id) return notFound();
    try {
      const resp = await fetch(window.AII.dataUrl(`articles/${id}.json`));
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      art = await resp.json();
    } catch (e) {
      return notFound();
    }
    render();
    document.addEventListener("aii:langchange", render);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
