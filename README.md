# 每日财经简报生成系统 - GitHub Actions 定时任务配置指南

## 📖 项目简介

这是一个基于 OpenAI 和 GitHub Actions 的自动化财经简报生成系统。它会每天定时抓取全球顶级财经媒体的热点内容，通过 AI 分析整理成结构化简报，并自动发布到 GitHub Pages。

### ✨ 核心特性

- ⏰ **全自动定时任务** - 每天自动运行，无需人工干预
- 🌐 **多源数据抓取** - RSS 新闻源 + A 股行业/概念板块资金流 + 重点龙头股行情
- 🤖 **AI 智能分析** - 优先使用 OpenAI API 自动筛选热点、提炼趋势
- 💰 **零成本运行** - GitHub Actions 个人使用完全免费
- 📱 **自动发布** - 生成 Markdown 和 HTML，支持 GitHub Pages 托管
- 🌐 **网站输出** - 首页、最新简报和历史归档自动更新
- 🎯 **重点赛道雷达** - 固定跟踪存储芯片、CPO、PCB、先进封装、光纤光缆、MLCC、大科技、海外基建/出海链等板块
- 🖼️ **资金流向图** - 每日生成 `digests/sector-flow.svg`，首页自动展示板块资金净流入/净流出排行

---

## 🚀 快速开始

### 步骤 1: 准备 GitHub 仓库

1. **创建或使用现有仓库**
   ```bash
   # 在你的 GitHub 账号下创建一个新仓库
   # 例如: daily-finance-digest
   ```

2. **将 skill 文件复制到仓库**
   ```bash
   cp -r ~/.claude/skills/daily-tech-digest/* ~/Projects/daily-finance-digest/
   cd ~/Projects/daily-finance-digest
   ```

### 步骤 2: 配置 GitHub Secrets

在 GitHub 仓库中配置以下 Secrets：

1. **打开仓库设置**
   - 进入你的 GitHub 仓库
   - 点击 `Settings` > `Secrets and variables` > `Actions`
   - 点击 `New repository secret`

2. **添加以下 Secrets**:
   ```
   Name: OPENAI_API_KEY
   Value: 你的 OpenAI API Key

   ```

   可选：如果想调整 OpenAI 模型，可以在 `Settings` > `Secrets and variables` > `Actions` > `Variables` 里添加：
   ```
   Name: OPENAI_MODEL
   Value: gpt-4.1-mini
   ```

### 步骤 3: 验证 GitHub Actions 配置

GitHub Actions 配置文件位于：
```
.github/workflows/daily-tech-digest.yml
```

配置说明：

```yaml
# 定时任务：每天北京时间 06:30 运行（UTC 前一天 22:30）
schedule:
  - cron: '30 22 * * *'

# 支持手动触发（用于测试）
workflow_dispatch: true
```

### 步骤 4: 测试运行

**方式1: 手动触发（推荐）**
1. 进入 `Actions` 标签页
2. 选择 `每日财经简报生成器` 工作流
3. 点击 `Run workflow` > `Run workflow`

**方式2: 等待定时触发**
- 系统会在每天北京时间 06:30 自动运行

---

## 📊 数据源配置

当前配置的财经媒体 RSS 源：

| 媒体 | 分类 | 覆盖内容 |
|------|------|----------|
| 36氪 | 科技财经 | 科技公司、产业动态 |
| 虎嗅 | 商业观察 | 商业趋势、产业观察 |
| 雪球 | 投资者社区 | 热点话题、市场讨论 |
| FT中文网 | 市场分析 | 国际市场、中国经济 |
| CNBC | 美股聚焦 | 美股市场、科技股 |

另有 A 股板块资金流数据：

| 数据 | 来源方式 | 覆盖内容 |
|------|----------|----------|
| 行业板块资金流 | AkShare / 东方财富资金流接口 | 行业板块涨跌幅、主力净流入、超大单净流入 |
| 概念板块资金流 | AkShare / 东方财富资金流接口 | 概念板块涨跌幅、主力净流入、超大单净流入 |
| 龙头股行情 | AkShare / 东方财富 A 股实时行情 | 重点赛道龙头股最新价、涨跌幅、成交额、换手率 |

### 重点赛道与龙头股

当前固定跟踪：

| 赛道 | 龙头股 |
|------|--------|
| 存储芯片 | 兆易创新、德明利、江波龙 |
| CPO | 中际旭创、新易盛、天孚通信 |
| PCB | 胜宏科技、沪电股份 |
| 先进封装 | 长电科技、华天科技、深科技 |
| 光纤光缆 | 长飞光纤、亨通光电、中天科技 |
| MLCC | 三环集团、风华高科、洁美科技 |
| 大科技 | 寒武纪、海光信息、中科曙光、工业富联、浪潮信息 |
| 海外基建/出海链 | 中国交建、中国电建、中工国际、徐工机械、三一重工 |
| 铜箔 | 铜冠铜箔、诺德股份、嘉元科技 |
| 覆铜板 | 金安国纪、华正新材、生益科技 |
| 氟化钙/萤石链 | 中船特气、中巨芯、昊华科技 |

### 如果要更细、更准，建议补充的 API

免费数据能覆盖“板块资金 + 龙头股行情 + 新闻归因”，但很难稳定拿到短线交易里最关键的“异动原因”。如果你有下面任一类 API，可以继续接入：

| API 类型 | 用途 |
|----------|------|
| 同花顺、东方财富、Choice、Wind 板块资金 API | 更稳定拿到完整行业/概念排行、历史资金、成分股贡献 |
| 财联社、电报、快讯 API | 把实时利好利空和板块异动关联起来 |
| 涨停原因/异动原因 API | 判断某个龙头上涨是订单、业绩、政策还是情绪炒作 |
| 个股公告 API | 跟踪减持、定增、订单、业绩预告、监管问询 |
| 研报/一致预期 API | 补充机构观点、盈利预测和估值变化 |
| ETF/北向/融资融券资金 API | 判断板块资金是短线游资、机构还是被动资金驱动 |

---

## 🌐 配置 GitHub Pages（可选）

如果想在线查看生成的简报：

### 步骤 1: 启用 GitHub Pages

1. 进入仓库 `Settings` > `Pages`
2. Source 选择:
   - **Source**: Deploy from a branch
   - **Branch**: `main` / `root`
3. 点击 `Save`

### 步骤 2: 访问在线页面

```
https://你的用户名.github.io/仓库名/digests/
```

---

## 💰 费用说明

### GitHub Actions
- ✅ **个人账户**：每月 2000 分钟免费
- ✅ **公共仓库**：完全免费
- 本次任务每次运行约 2-3 分钟

### OpenAI API
- 默认模型可通过 `OPENAI_MODEL` 变量调整
- 每次生成简报约消耗 3000-5000 tokens，具体费用取决于所选模型
- 脚本仍保留 Anthropic/智谱兼容接口兜底，但 GitHub Actions 默认走 OpenAI

---

## 📈 输出文件

- `digests/YYYY-MM-DD.md` - 按日期归档的简报
- `digests/latest.md` - 最新简报
- `digests/sector-flow.svg` - 首页展示的板块资金流向图
- `digests/index.html` - HTML 索引页面
- `index.html` - GitHub Pages 首页，展示最新简报和最近归档

简报内容结构：
- 🔥 今日热点
- 📈 市场动态
- 🧭 今日板块资金流向
- 🎯 重点赛道雷达
- 💰 宏观与政策
- 🏢 产业要闻
- 🔎 板块利好利空归因
- ⚡ 明日板块观察清单

---

**创建时间**: 2026-01-18
**维护者**: Tina
**许可证**: MIT
