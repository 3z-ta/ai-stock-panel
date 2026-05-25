# AI 股票分析面板

实时股票行情 + DeepSeek AI 智能分析，支持美股和 A 股。

在线访问: https://ai-stock-panel-production.up.railway.app

## 功能

- **美股**: 通过 yfinance 获取实时行情（AAPL、TSLA、MSFT 等）
- **A股**: 通过 akshare 获取实时行情（600519、000001 等）
- **AI 分析**: DeepSeek-v4-pro 模型分析股票走势、情绪和风险等级
- **数据存储**: 分析结果存储到 Supabase

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY、SUPABASE_URL、SUPABASE_KEY
uvicorn app:app --host 0.0.0.0 --port 10000
```

访问 http://localhost:10000

## API

### GET /api/stock/{code}

获取股票实时数据及 AI 分析。

```
GET /api/stock/AAPL
GET /api/stock/600519
```

返回示例:

```json
{
  "stock_data": {
    "code": "AAPL",
    "name": "Apple Inc.",
    "price": 175.32,
    "change_pct": 1.23,
    "volume": 52100000,
    "high_52w": 199.62,
    "low_52w": 143.90,
    "market": "US"
  },
  "analysis": {
    "summary": "苹果股价接近52周高点，成交量温和，技术面看涨但估值偏高需注意回调风险。",
    "sentiment": "Bullish",
    "risk_level": "Medium"
  },
  "timestamp": "2026-05-25T12:00:00Z"
}
```

### GET /api/health

健康检查。

## 环境变量

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `OPENAI_BASE_URL` | DeepSeek API 端点 |
| `SUPABASE_URL` | Supabase 项目 URL |
| `SUPABASE_KEY` | Supabase 匿名密钥 |

## Supabase 表结构

```sql
CREATE TABLE stock_analyses (
  id BIGSERIAL PRIMARY KEY,
  stock_code TEXT NOT NULL,
  stock_data JSONB,
  analysis JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Railway 部署

1. 将项目推送到 GitHub 仓库
2. 在 Railway.com 用 GitHub 登录
3. New Project → Deploy from GitHub repo → 选择仓库
4. Railway 自动识别 `railway.toml` 配置
5. 在 Variables 中添加环境变量：
   - `DEEPSEEK_API_KEY` — DeepSeek API 密钥
   - `OPENAI_BASE_URL` — https://api.deepseek.com
   - `SUPABASE_URL` — Supabase 项目 URL
   - `SUPABASE_KEY` — Supabase 匿名密钥
6. 添加变量后自动重新部署，通过 `xxx.up.railway.app` 访问

## 技术栈

- **后端**: FastAPI + uvicorn
- **数据**: yfinance (美股) + akshare (A股)
- **AI**: deepseek-v4-pro (OpenAI 兼容 API)
- **存储**: Supabase
- **前端**: 原生 HTML/CSS/JS

---

## Prompt 设计 — 强制 JSON 输出

### System Prompt（完整代码）

```
你是一个专业的股票分析师。用户会提供一支股票的实时行情数据，你需要根据这些数据给出简明的分析结论。
你必须严格返回一个 JSON 对象，格式如下：
{
  "summary": "一句话总结该股票当前的表现和短期展望（中文，不超过50字）",
  "sentiment": "Bullish" 或 "Neutral" 或 "Bearish",
  "risk_level": "High" 或 "Medium" 或 "Low"
}
不要输出任何其他文字、注释、Markdown 标记或解释。只输出上述 JSON。
```

### JSON 强制策略

1. **System Prompt 约束**: 明确要求"不要输出任何其他文字、注释、Markdown 标记或解释"
2. **低温度采样**: `temperature=0.3`，减少模型随机性，提高输出稳定性
3. **正则后处理兜底**: 即使模型偶尔返回 Markdown 代码块，`extract_json()` 函数也能提取纯 JSON

### 核心代码

```python
def extract_json(raw: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("No valid JSON found in response")
```

---

## Debug 记录 — JSON 解析失败

### 现象

调用 DeepSeek API 后，`json.loads()` 间歇性抛出 `JSONDecodeError`，导致接口返回 500 错误。

### 排查过程

1. 打印 LLM 原始返回内容，发现模型偶尔返回 Markdown 代码块格式：
   ```
   ```json
   {"summary": "...", "sentiment": "Bullish", "risk_level": "Medium"}
   \```
   ```

2. 确认原因：虽然 System Prompt 要求"不要使用 Markdown 代码块"，但模型在低概率下仍会违反该约束。

### 解决方案

1. **增强 System Prompt**: 加入"不要输出任何文字、注释、Markdown 标记"的明确约束
2. **实现 `extract_json()` 函数**: 先用 `json.loads()` 直接解析；失败后回退到正则 `re.search(r'\{.*\}', raw, re.DOTALL)` 提取 `{...}` 内容，无论外层包裹什么格式都能正确提取

### 效果

修改后 API 再未出现 JSON 解析错误，即使模型返回非标准格式也能正确提取。

---
