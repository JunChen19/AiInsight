/* 列表页：加载 index.json → 日期分组 → 分类/搜索过滤 → 渲染 */
(function () {
  "use strict";

  const $ = (s) => document.querySelector(s);
  const esc = window.AII_MD.esc;

  let all = [];          // 全部条目
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  let cat = lsGet("aii-cat") || "all";
  let q = "";

  function parseDate(ts) {
    if (!ts) return null;
    const d = new Date(ts);
    return isNaN(d) ? null : d;
  }

  function dateKey(e) {
    const d = parseDate(e.published || e.fetched_at);
    return d ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}` : "—";
  }

  function escAttr(s) { return esc(String(s ?? "")); }

  function itemHtml(e) {
    const t = window.AII;
    const d = parseDate(e.published || e.fetched_at);
    const isRl = e.category === "rl";
    const chipCls = isRl ? "chip is-rl" : (e.category === "model-release" ? "chip is-release" : "chip");
    const tags = (e.tags || []).map((x) => `<span class="tag">${escAttr(x)}</span>`).join("");
    const typeBadge = e.type === "paper" ? `<span class="item-type" data-t="paper"></span>` : "";
    return `
      <article class="item ${isRl ? "is-rl" : ""}">
        <div class="item-topline">
          <span class="${chipCls}">${esc(t.catLabel(e.category))}</span>
          <span class="item-source">
            ${escAttr(e.source_name)}<span class="sep">/</span>${d ? t.t("timeFmt")(d.getHours(), d.getMinutes()) : ""}
          </span>
          ${typeBadge}
        </div>
        <h2 class="item-title"><a href="article.html?id=${encodeURIComponent(e.id)}">${escAttr(t.titleOf(e))}</a></h2>
        <p class="item-summary">${escAttr(t.summaryOf(e))}</p>
        <div class="item-tags">${tags}</div>
      </article>`;
  }

  function render() {
    const t = window.AII;
    const kw = q.trim().toLowerCase();
    const shown = all.filter((e) => {
      if (cat !== "all" && e.category !== cat) return false;
      if (kw) {
        const hay = [e.title_en, e.title_zh, e.summary_en, e.summary_zh,
                     e.source_name, (e.tags || []).join(" ")].join(" ").toLowerCase();
        if (!hay.includes(kw)) return false;
      }
      return true;
    });

    // 报头更新时间
    const metaEl = $("#latest");
    if (metaEl && all.length) {
      const d = parseDate(all[0].fetched_at || all[0].published);
      if (d) metaEl.textContent = `${t.t("latest")} ${dateKey(all[0])}`;
    }

    // 分类计数
    const counts = { all: all.length };
    all.forEach((e) => { counts[e.category] = (counts[e.category] || 0) + 1; });
    document.querySelectorAll(".cat-tab").forEach((b) => {
      const c = b.dataset.cat;
      const n = b.querySelector(".n");
      if (n) n.textContent = counts[c] || 0;
    });

    const main = $("#list");
    if (!shown.length) {
      const isErr = !all.length && window.__aiiLoadFailed;
      main.innerHTML = `
        <div class="state-box">
          <div class="big">${esc(t.t(isErr ? "errTitle" : "emptyTitle"))}</div>
          <p>${esc(t.t(isErr ? "errBody" : "emptyBody"))}</p>
          ${isErr ? `<p><a href="." onclick="location.reload();return false;">${esc(t.t("retry"))}</a></p>` : ""}
        </div>`;
      return;
    }

    // 按日期分组
    const groups = new Map();
    shown.forEach((e) => {
      const k = dateKey(e);
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(e);
    });

    const parts = [];
    const sortedKeys = [...groups.keys()].sort((a, b) => b.localeCompare(a)); // 日期降序
    for (const k of sortedKeys) {
      const items = groups.get(k);
      const [y, m, d] = k.split("-").map(Number);
      const wd = new Date(y, m - 1, d).getDay();
      parts.push(`
        <section class="day-row">
          <div class="day-spine">
            <div class="d-month">${esc(t.t("dateFmt")(y, m, d))}</div>
            <div class="d-week">${esc(t.t("weekdays")[wd])}</div>
            <div class="d-count">${items.length} ${esc(t.t("entryUnit"))}</div>
          </div>
          <div class="day-items">${items.map(itemHtml).join("")}</div>
        </section>`);
    }
    main.innerHTML = parts.join("");
  }

  function bindFilters() {
    document.querySelectorAll(".cat-tab").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.cat === cat));
      b.addEventListener("click", () => {
        cat = b.dataset.cat;
        lsSet("aii-cat", cat);
        document.querySelectorAll(".cat-tab").forEach((x) =>
          x.setAttribute("aria-pressed", String(x.dataset.cat === cat)));
        render();
      });
    });
    const search = $("#search");
    if (search) {
      search.addEventListener("input", () => { q = search.value; render(); });
    }
  }

  function fixTypeBadges() {
    document.querySelectorAll("[data-t=paper]").forEach((el) => {
      el.textContent = window.AII.t("paper");
    });
  }

  async function boot() {
    bindFilters();
    try {
      const resp = await fetch(window.AII.dataUrl("index.json"));
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      all = await resp.json();
    } catch (e) {
      console.error("index.json 加载失败:", e);
      window.__aiiLoadFailed = true;
      all = [];
    }
    render();
    fixTypeBadges();
    document.addEventListener("aii:langchange", () => { render(); fixTypeBadges(); });
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
