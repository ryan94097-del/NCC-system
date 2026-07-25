# NCC 賣場自動核對 — Streamlit Cloud 版

自動到 **Yahoo購物 / MOMO / 露天** 搜尋、讀取賣場標示的 **NCC 認證碼**，比對清單並確認型號一致；
依年份對 **LPD / TTE** 並依據 **CCAN** 與 **其他 RCB** 進行雙池隨機抽樣，**湊不滿會自動找下一筆**直到補齊。
酷澎 / 蝦皮 / Google 僅提供手動搜尋連結。

## 🎯 CCAN 雙池抽樣與多層搜尋策略
- **CCAN 池**：自家驗證機構 (`AN`) 專屬抽樣池
- **其他 RCB 池**：其餘驗證機構的抽樣池
- LPD 與 TTE 各自獨立雙池配額設定
- **多層搜尋策略**：
  - 第 1 輪：品牌 + 型號
  - 第 2 輪：品牌 + 型號 + 產品類別（補強短型號）
  - 第 3 輪：NCC ID 搜尋

## 檔案
- `app.py` — Streamlit 介面（共用密碼、上傳、雙池設定、執行、進度顯示、結果分頁、CSV/Excel 匯出）
- `.streamlit/config.toml` — 深色科技風 UI 主題設定
- `ncc_core.py` — Excel 解析、證號索引、雙池分割邏輯
- `scrapers.py` — Yahoo / MOMO / 露天自動抓取邏輯
- `verify.py` — 包含 `run_dual_pool` 雙池抽樣與核對
- `requirements.txt` — 依賴套件

## 部署到 Streamlit Community Cloud（免費）

1. 到 <https://share.streamlit.io> 用 GitHub 登入。
2. **New app** → 選擇對應的 repo 與 branch，**Main file path** 填 `streamlit_app/app.py`。
3. **Advanced settings → Secrets** 貼上（設定共用密碼）：
   ```toml
   app_password = "你的密碼"
   ```
   （未設定則預設使用 `ncc2026`）
4. **Deploy**。完成後會得到一個 `https://xxxx.streamlit.app` 網址，同事開啟網址、輸入密碼即可使用。

> ⚠️ 部署前先與公司 IT 確認：可否連 `*.streamlit.app`、可否在外部網站上傳這份清單資料。

## 本機測試
```powershell
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```

## 注意 / 限制
- 只有 **Yahoo / MOMO** 較容易自動讀取 NCC ID。
- **MOMO 逐頁抓取**較慢、請求量大；可在「進階設定」調整速度以避免被封鎖。
- 大量請求可能被限流，請溫和使用。
- 確認標準：賣場讀到的 NCC ID **存在清單** 且 **型號一致**。
