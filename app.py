import os
import re
import json
from datetime import datetime

import yfinance as yf
import akshare as ak
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Stock Analysis Panel")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DeepSeek client (OpenAI-compatible)
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
deepseek = None
if deepseek_api_key:
    deepseek = OpenAI(
        api_key=deepseek_api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
    )

# Supabase client (only if configured)
supabase_url = os.getenv("SUPABASE_URL", "")
supabase_key = os.getenv("SUPABASE_KEY", "")
supabase = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)

SYSTEM_PROMPT = """你是一个专业的股票分析师。用户会提供一支股票的实时行情数据，你需要根据这些数据给出简明的分析结论。
你必须严格返回一个 JSON 对象，格式如下：
{
  "summary": "一句话总结该股票当前的表现和短期展望（中文，不超过50字）",
  "sentiment": "Bullish" 或 "Neutral" 或 "Bearish",
  "risk_level": "High" 或 "Medium" 或 "Low"
}
不要输出任何其他文字、注释、Markdown 标记或解释。只输出上述 JSON。"""


def extract_json(raw: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("No valid JSON found in response")


def detect_market(code: str) -> str:
    """Detect market type from stock code."""
    code = code.upper().strip()
    if code.isdigit():
        return "a_share"
    return "us"


def fetch_us_stock(code: str) -> dict:
    ticker = yf.Ticker(code)
    info = ticker.info
    fast = ticker.fast_info
    return {
        "code": code,
        "name": info.get("shortName", code),
        "price": getattr(fast, "last_price", None) or info.get("currentPrice"),
        "change_pct": info.get("regularMarketChangePercent"),
        "volume": info.get("regularMarketVolume"),
        "high_52w": info.get("fiftyTwoWeekHigh"),
        "low_52w": info.get("fiftyTwoWeekLow"),
        "market": "US",
    }


def fetch_a_stock(code: str) -> dict:
    df = ak.stock_zh_a_spot_em()
    row = df[df["代码"] == code]
    if row.empty:
        raise ValueError(f"A-share stock {code} not found")
    r = row.iloc[0]
    return {
        "code": code,
        "name": r.get("名称", code),
        "price": float(r["最新价"]) if r["最新价"] != "-" else None,
        "change_pct": float(r["涨跌幅"]) if r["涨跌幅"] != "-" else None,
        "volume": int(r["成交量"]) if r["成交量"] != "-" else None,
        "high_52w": None,
        "low_52w": None,
        "market": "A股",
    }


def analyze_stock(stock_data: dict) -> dict:
    if not deepseek:
        return {
            "summary": "未配置 DEEPSEEK_API_KEY，无法进行 AI 分析",
            "sentiment": "Neutral",
            "risk_level": "Medium",
        }

    user_prompt = f"""股票代码：{stock_data['code']}
当前价格：{stock_data['price']}
涨跌幅：{stock_data['change_pct']}%
成交量：{stock_data['volume']}
52周高点：{stock_data.get('high_52w', 'N/A')}
52周低点：{stock_data.get('low_52w', 'N/A')}
请分析。"""

    resp = deepseek.chat.completions.create(
        model="deepseek-v4-pro",
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = resp.choices[0].message.content
    return extract_json(raw)


def save_analysis(stock_data: dict, analysis: dict):
    if not supabase:
        return
    try:
        supabase.table("stock_analyses").insert({
            "stock_code": stock_data["code"],
            "stock_data": json.dumps(stock_data, default=str),
            "analysis": json.dumps(analysis, default=str),
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass  # non-critical


@app.get("/api/stock/{code}")
async def get_stock(code: str):
    try:
        market = detect_market(code)
        if market == "us":
            stock_data = fetch_us_stock(code)
        else:
            stock_data = fetch_a_stock(code)

        analysis = analyze_stock(stock_data)
        save_analysis(stock_data, analysis)

        return {
            "stock_data": stock_data,
            "analysis": analysis,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="dist", html=True), name="static")
