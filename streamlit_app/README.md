# NCC 賣場自動核對 — Streamlit Cloud 版

自動到 **Yahoo購物 / MOMO** 搜尋、讀取賣場標示的 **NCC 認證碼**，比對你的清單並確認型號一致；
依年份對 **LPD / TTE** 各自筆數**隨機抽樣**，**湊不滿會自動找下一筆**直到補齊。
酷澎 / 蝦皮 / Google / 露天 無法自動讀 ID，僅提供手動搜尋連結。

## 檔案
- `app.py` — Streamlit 介面（共用密碼、上傳、設定、執行、結果、CSV 匯出）
- `ncc_core.py` — Excel 解析、證號索引、關鍵字
- `scrapers.py` — Yahoo / MOMO 抓取；其他賣場手動連結
- `verify.py` — 單筆比對 + `run_pool` 抽樣湊筆數（純函式，已離線+實測）
- `requirements.txt` — 相依套件

## 部署到 Streamlit Community Cloud（免費）

1. 到 <https://share.streamlit.io> 用 GitHub 登入（授權存取 `ryan94097-del/NCC-system`）。
2. **New app** → 選 repo `ryan94097-del/NCC-system`、branch `main`、
   **Main file path** 填 `streamlit_app/app.py`。
3. **Advanced settings → Secrets** 貼上（設定共用密碼）：
   ```
   app_password = "你的密碼"
   ```
   （不設就用預設 `ncc2026`。）
4. **Deploy**。完成後會得到一個 `https://xxxx.streamlit.app` 網址，同事開網址、輸入密碼即可用。

> ⚠️ 部署前先與公司 IT 確認：可否連 `*.streamlit.app`、可否在外部網站上傳這份清單資料。

## 本機測試
```powershell
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```

## 注意 / 限制
- 只有 **Yahoo / MOMO** 能自動讀 NCC ID（實測依據見 `docs/DECISIONS.md`）。
- **MOMO 逐頁抓取**較慢、請求量大；用側邊欄「每筆最多抓幾個商品頁」「請求間隔」「每分類最多嘗試筆數」控制速度與被封風險。
- 自動化依賴賣場不改版/不封鎖；大量請求可能被限流，請溫和使用。
- 確認標準：賣場讀到的 NCC ID **存在清單** 且 **型號一致**（可於 `verify.py` 調整）。
