const input = document.getElementById("stockInput");
const btn = document.getElementById("searchBtn");
const loading = document.getElementById("loading");
const error = document.getElementById("error");
const result = document.getElementById("result");

btn.addEventListener("click", analyze);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") analyze();
});

async function analyze() {
  const code = input.value.trim();
  if (!code) return;

  loading.classList.remove("hidden");
  error.classList.add("hidden");
  result.classList.add("hidden");
  btn.disabled = true;

  try {
    const resp = await fetch(`/api/stock/${encodeURIComponent(code)}`);
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "请求失败");
    }
    const data = await resp.json();
    render(data);
  } catch (e) {
    error.textContent = e.message;
    error.classList.remove("hidden");
  } finally {
    loading.classList.add("hidden");
    btn.disabled = false;
  }
}

function render(data) {
  const sd = data.stock_data;
  const an = data.analysis;

  document.getElementById("stockName").textContent = sd.name || sd.code;
  document.getElementById("stockCode").textContent = sd.code;
  document.getElementById("marketBadge").textContent = sd.market || "--";

  document.getElementById("stockPrice").textContent =
    sd.price != null ? `$${Number(sd.price).toFixed(2)}` : "--";

  const chg = document.getElementById("stockChange");
  if (sd.change_pct != null) {
    const val = Number(sd.change_pct);
    chg.textContent = `${val >= 0 ? "+" : ""}${val.toFixed(2)}%`;
    chg.className = `change ${val > 0 ? "positive" : val < 0 ? "negative" : "neutral"}`;
  } else {
    chg.textContent = "--";
    chg.className = "change neutral";
  }

  document.getElementById("stockVolume").textContent =
    sd.volume != null ? Number(sd.volume).toLocaleString() : "--";
  document.getElementById("stockHigh").textContent =
    sd.high_52w != null ? `$${Number(sd.high_52w).toFixed(2)}` : "--";
  document.getElementById("stockLow").textContent =
    sd.low_52w != null ? `$${Number(sd.low_52w).toFixed(2)}` : "--";
  document.getElementById("stockMarket").textContent = sd.market || "--";

  document.getElementById("summary").textContent = an.summary || "--";

  const sent = document.getElementById("sentiment");
  sent.textContent = an.sentiment || "--";
  sent.setAttribute("data-type", an.sentiment);

  const risk = document.getElementById("riskLevel");
  risk.textContent = `风险: ${an.risk_level || "--"}`;
  risk.setAttribute("data-type", an.risk_level);

  document.getElementById("timestamp").textContent =
    `分析时间: ${new Date(data.timestamp).toLocaleString("zh-CN")}`;

  result.classList.remove("hidden");
}
