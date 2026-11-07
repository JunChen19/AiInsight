# AiInsight

每日自动更新的 AI 资讯站：抓取模型发布、模型新技术（重点强化学习方向，含功能 / 性能 / 精度）相关新闻，AI 生成中英双语概括并翻译全文。

- 线上地址：`https://junchen19.github.io/AiInsight/`
- 架构：GitHub Actions 每日定时运行 Python 采集管道 → 生成 JSON 数据与图片并提交回仓库 → GitHub Pages 自动发布
- 概括与翻译由 DeepSeek API 生成（API key 存于仓库 Secrets，不出现在代码中）

## 目录结构

```
pipeline/   采集与处理管道（Python）
site/       纯静态前端（零构建）
data/       生成的数据（index.json / articles/ / images/）
.github/    定时任务与 Pages 部署工作流
```

## 首次部署

见 [docs/SETUP.md](docs/SETUP.md)，只需三步：配置 API Secret → 开启 Pages → 手动触发一次工作流。

## 手动运行（本地调试）

```bash
cd pipeline
pip install -r requirements.txt
DEEPSEEK_API_KEY=你的key python main.py
```
