# 部署指引（首次上线，约 5 分钟）

## 第 0 步：把代码推到 GitHub

在本地项目目录（`Insight2`）打开终端：

```bash
git remote add origin https://github.com/JunChen19/AiInsight.git
git push -u origin main
```

> 如果本机没配置过 GitHub 凭据，Windows 上首次 push 会弹出 GitHub 登录窗口，按提示登录即可。

## 第 1 步：配置 DeepSeek API Secret

1. 打开仓库页面 → **Settings** → 左侧 **Secrets and variables** → **Actions**
2. 点 **New repository secret**
3. Name 填：`DEEPSEEK_API_KEY`
4. Secret 填：你的 DeepSeek API key（`sk-` 开头）
5. 点 **Add secret**

> key 只存在 GitHub 加密的 Secrets 里，代码和日志中都不会出现。

## 第 2 步：开启 GitHub Pages

1. **Settings** → 左侧 **Pages**
2. **Source** 选择 **GitHub Actions**（不是 Deploy from a branch）
3. 保存

## 第 3 步：手动触发第一次运行

1. 仓库页 → **Actions** 标签 → 左侧选 **Daily digest**
2. 点右侧 **Run workflow** → **Run workflow**
3. 等待运行完成（约 3~6 分钟），完成后访问：

```
https://junchen19.github.io/AiInsight/
```

之后每天北京时间早晨 6:30 左右自动运行（GitHub 的定时任务可能有几分钟到半小时的排队延迟，属正常现象）。

---

# 日常使用

## 想立即更新内容

Actions → Daily digest → Run workflow，随时手动触发。

## 添加 / 调整新闻源

编辑 `pipeline/sources.py` 里的 `SOURCES` 列表（RSS 地址 + 名称 + 优先级），提交即可。

## 更换 LLM 提供商（不用改代码）

流水线使用 OpenAI 兼容接口。在仓库 Settings → Secrets → Actions 中新增两个 Secret（可选）：

| Secret | 作用 | 默认值 |
|---|---|---|
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-chat` |

## 调整每日篇数

`pipeline/config.py` 中 `MAX_PER_DAY`（默认 9），或给 Actions 加环境变量 `MAX_ARTICLES`。

## 本地调试

```bash
cd pipeline
pip install -r requirements.txt
DEEPSEEK_API_KEY=你的key python main.py
```

## 成本参考

每日 5~10 篇（含全文中文翻译），deepseek-chat 约消耗每天 ¥0.1 ~ ¥0.5。

## 故障排查

- **Actions 运行失败，日志提示缺少 DEEPSEEK_API_KEY**：第 1 步的 Secret 名称拼写是否完全一致
- **网站 404**：确认第 2 步 Source 选的是 GitHub Actions，且已成功运行过一次工作流
- **某天没更新**：看 Actions 日志；单个新闻源失败属正常（自动跳过），全部失败才需要排查
- **抓取成功但网站没更新**（日志出现 "No artifacts named github-pages were found"）：GitHub Pages 部署接口的瞬时故障。打开 Actions → **Republish site** → Run workflow 一键重新发布，无需重新抓取
- **想重抓某篇文章**：删掉 `data/articles/` 对应 JSON 并从 `data/index.json` 移除条目，下次运行会重新遇到它
