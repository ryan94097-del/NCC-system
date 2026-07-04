# NCC 案件賣場搜尋核對系統

協助 NCC 型式認證產品的**市場監督核對**：讀取認證清單 Excel → 篩選 → 為每筆產品產生六大電商賣場「一鍵搜尋連結」→ 人工核對並記錄證據 → 匯出報告。

## 這是什麼

一個**純前端單一 HTML 工具**，在**公司鎖定電腦**上也能用：雙擊即開、零安裝、免 Python、離線可跑。

它不是自動爬蟲，而是**智慧待查清單 + 一鍵多賣場搜尋啟動器 + 核對紀錄表**——把「手動一筆筆複製型號、切換六個網站貼上搜尋」的苦工自動化。

## 功能

- 上傳 Excel/CSV，自動抓表頭、分流 LPD / TTE、清洗雜訊。
- 依年份（證書編號年份碼）篩選、去重。
- 每筆產品產生 MOMO / Yahoo / Google 購物 / 露天 / 酷澎 / 蝦皮 搜尋連結（排除 PChome）。
- 核對工作表：狀態標記、備註、手動填價、賣家、拖放截圖。
- 匯出 CSV（無亂碼）/ Excel。

## 給 AI 協作代理

**請先讀 [`AGENTS.md`](AGENTS.md)**，再依需要展開 `docs/`：
- [`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md) — 硬性限制
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 架構與資料結構
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — 決策紀錄

## 快速開始

1. 雙擊 `dist/NCC核對工具.html`，輸入密碼 `ncc2026`。
2. 上傳認證清單 Excel（或按「載入測試樣本」）。
3. 點各賣場按鈕搜尋 → 填狀態/價格/截圖 → 匯出報告。

詳見 [`docs/USAGE.md`](docs/USAGE.md)。換密碼用 `dist/builder.html`。

## 狀態

✅ 主工具完成並實測通過（2026-07-04）。

## 注意

真實認證資料（`*.xlsx`）不納入本 repo（隱私考量，見 `.gitignore`）。
