/* 轻量 Markdown 渲染器（覆盖 trafilatura 输出子集 + 翻译保持的格式）
   安全策略：所有文本先做 HTML 转义，再套用受限的 Markdown 语法。 */
(function () {
  "use strict";

  function esc(s) {
    return s
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function inline(s) {
    let out = esc(s);
    out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    // 链接：仅 http(s)，白名单属性
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return out;
  }

  function render(md) {
    if (!md) return "";
    const lines = String(md).replace(/\r\n?/g, "\n").split("\n");
    const html = [];
    let i = 0, para = [], list = null, table = null, code = null;

    const flushPara = () => {
      if (para.length) { html.push("<p>" + para.map(inline).join("<br>") + "</p>"); para = []; }
    };
    const flushList = () => {
      if (list) { html.push(`</${list.tag}>`); list = null; }
    };
    const flushTable = () => {
      if (table) { html.push("</tbody></table>"); table = null; }
    };
    const flushAll = () => { flushPara(); flushList(); flushTable(); };

    while (i < lines.length) {
      const line = lines[i];

      // 代码块
      if (code === null && /^\s*```/.test(line)) {
        flushAll();
        code = [];
        i++;
        continue;
      }
      if (code !== null) {
        if (/^\s*```/.test(line)) {
          html.push("<pre><code>" + esc(code.join("\n")) + "</code></pre>");
          code = null;
        } else {
          code.push(line);
        }
        i++;
        continue;
      }

      // 表格（| a | b |）
      if (/^\s*\|/.test(line)) {
        const cells = line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        if (cells.every((c) => /^:?-{2,}:?$/.test(c))) { i++; continue; } // 分隔行
        if (!table) {
          flushPara(); flushList();
          html.push("<table><thead><tr>" +
            cells.map((c) => "<th>" + inline(c) + "</th>").join("") + "</tr></thead><tbody>");
          table = true;
        } else {
          html.push("<tr>" + cells.map((c) => "<td>" + inline(c) + "</td>").join("") + "</tr>");
        }
        i++;
        continue;
      }
      flushTable();

      // 标题
      const h = line.match(/^(#{1,4})\s+(.*)$/);
      if (h) { flushAll(); html.push(`<h${h[1].length}>` + inline(h[2]) + `</h${h[1].length}>`); i++; continue; }

      // 水平线
      if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { flushAll(); html.push("<hr>"); i++; continue; }

      // 引用
      if (/^\s*>\s?/.test(line)) { flushAll(); html.push("<blockquote>" + inline(line.replace(/^\s*>\s?/, "")) + "</blockquote>"); i++; continue; }

      // 列表
      const ul = line.match(/^\s*[-*+]\s+(.*)$/);
      const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (ul || ol) {
        flushPara();
        const tag = ul ? "ul" : "ol";
        if (!list || list.tag !== tag) { flushList(); html.push(`<${tag}>`); list = { tag }; }
        html.push("<li>" + inline((ul || ol)[1]) + "</li>");
        i++;
        continue;
      }
      flushList();

      // 空行
      if (!line.trim()) { flushPara(); i++; continue; }

      // 普通段落
      para.push(line.trim());
      i++;
    }
    if (code !== null) html.push("<pre><code>" + esc(code.join("\n")) + "</code></pre>");
    flushAll();
    return html.join("\n");
  }

  window.AII_MD = { render, esc };
})();
