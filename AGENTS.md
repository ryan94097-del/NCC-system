# AGENTS.md — AI 協作代理必讀

> 這份檔案是所有 AI 代理（Claude Code、Antigravity 等）進入本專案的**唯一入口**。
> 先讀本檔，再依需要展開 `docs/`。**不要**重新推導已寫在這裡的結論。

---

## 1. 專案一句話

打造一個**純前端單一 HTML 工具**，協助 NCC 型式認證產品的**市場監督核對**：
讀取認證清單 Excel → 篩選 → 為每筆產品產生六大電商賣場「一鍵搜尋連結」→ 人工核對並記錄證據 → 匯出報告。

## 2. ⛔ 硬性限制（違反即整個方案不可行，務必遵守）

1. **交付物只能是單一 `.html` 檔**（可內嵌 JS/CSS/函式庫）。雙擊即用、零安裝、離線可跑。
2. **不能用 Python / Node / 任何後端 / 任何需安裝的執行環境。** 使用端是**公司鎖定電腦**（禁裝軟體、無 Python、網路受監控）。
3. **不能依賴 CDN**：SheetJS 等函式庫必須**內嵌**進 HTML，因為公司網路可能擋外部資源。
4. **無法自動爬蟲/截圖/抓價**：瀏覽器 CORS + 無後端 + 鎖定網路 → 物理上做不到。
   這些改為「一鍵搜尋連結 + 人工點開看 + 手動填價/貼截圖」的工作表模式。
5. **排除 PChome**。
6. ❌ 不要再提議 Streamlit / Playwright / .exe 打包 / Vercel / 雲端部署 — 這些都已被上述限制否決，理由見 `docs/DECISIONS.md`。

完整背景見 [`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md)。

## 3. 交付物與功能範圍

主檔：`NCC核對工具.html`（單一檔）。功能：

- 上傳 Excel/CSV → 自動抓**第 2 列表頭**、分流 **LPD / TTE**、清洗雜訊列。
- **年份過濾**（證書編號第 5–6 碼 = 年份碼，如 `26` = 2026）、去重、分類統計。
- 每筆產品產生六大賣場搜尋連結：**MOMO、Yahoo 購物、Google 購物、露天、酷澎(Coupang)、蝦皮**（排除 PChome）。
- 智慧關鍵字：優先「廠牌 + 型號」；型號過短/通用時補產品類別詞。
- **核對工作表**：狀態標記（未查/已上架/未上架/存疑）、備註、手動填價、賣家名、拖放貼上截圖（base64 內嵌）。
- **搜尋模式切換**：完整清單 / 每分類只列前 N 筆（抽樣）。
- 匯出 CSV（`utf-8-sig` 無亂碼）/ Excel，含上述人工填入的證據。
- **共用密碼登入**：工具本體以 Web Crypto **AES-GCM 加密**，輸對共用密碼才解得開（詳見 `docs/ARCHITECTURE.md` §6）。另附純 HTML 的 `builder.html` 供在瀏覽器內更新內容/換密碼、重新產生加密檔（免 Python）。

資料結構、賣場 URL 樣式、關鍵字策略等細節見 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 4. 目前狀態

- ✅ 需求釐清、限制確認、資料結構實測完成。
- ✅ 協作文件建立。
- ✅ **主工具完成並實測通過**（2026-07-04）：
  - `src/app.js`：完整工具邏輯（解析/篩選/六賣場連結/核對表/localStorage/匯出 HTML+xlsx+CSV+進度）。
  - `dist/NCC核對工具.html`：加密單一檔（密碼 `ncc2026`），已於瀏覽器實測：對/錯密碼、Excel 解析、年份過濾、連結、編輯、匯出、截圖皆正常，無 console 錯誤。
  - `dist/builder.html`：換密碼/更新用的瀏覽器加密器（免 Python）。
  - `sample/NCC_測試樣本.xlsx`：去識別化測試樣本。
- 使用/重建流程見 [`docs/USAGE.md`](docs/USAGE.md)。
- 🗑️ 舊版 `app.py` / `test_search.py`（Python + Streamlit）為**已廢棄方向**，不在 repo（見 `.gitignore`），請勿沿用。

- ✅ **v1.1（2026-07-04）**：LPD/TTE 各自筆數的**隨機抽樣**+🎲重抽；每列「賣場 NCC ID / 賣場型號」欄位，以全清單證號索引**自動比對**（ID 存在清單即相符、型號寬鬆自動比對），結論徽章；匯出含比對欄位。實測全通過。

- ✅ **v2（2026-07-04）Streamlit Cloud 版**（`streamlit_app/`）：**真正自動化**——到 Yahoo購物/MOMO 搜尋、讀取賣場 NCC 認證碼、比對清單+型號一致；LPD/TTE 各自筆數隨機抽樣，**湊不滿自動找下一筆**。實測 Yahoo(TP-Link)、MOMO(Roborock) 皆能確認；fill-to-count 邏輯通過。其他賣場(酷澎403/蝦皮API/Google)只給手動連結。部署見 `streamlit_app/README.md`。

### 兩條並行路線（重要）
- **`src/` + `dist/`｜純 HTML 版**：公司鎖定機、離線、零安裝、無資料外流。手動點賣場 + 人工/自動輔助比對。
- **`streamlit_app/`｜Streamlit Cloud 版**：網址版、可自動抓 Yahoo/MOMO 的 NCC ID。**前提**：公司需放行 `*.streamlit.app` 且資料政策允許上傳。
- 兩者共用同一套解析/比對規則，改邏輯時注意兩邊一致。

### 下一步可能的優化（待使用者提出）
- 用真實 Excel 全量跑一次微調關鍵字/清洗規則。
- 賣場 URL 若改版需更新（HTML 版 `src/app.js` 的 `MARKETS`；Streamlit 版 `streamlit_app/scrapers.py`）。
- Yahoo/MOMO 版面若改版，更新 `streamlit_app/scrapers.py` 的解析。

## 5. 給協作代理的守則

- 先讀 `AGENTS.md` → `docs/CONSTRAINTS.md` → `docs/ARCHITECTURE.md` → `docs/DECISIONS.md`。
- 有重大決策/方向改變，請追加到 `docs/DECISIONS.md`（append，附日期）。
- 任何改動都要能通過第 2 節的硬性限制檢查。
- 使用者慣用繁體中文；介面文字、註解、說明都用繁體中文。
- **真實資料檔（`*.xlsx`）不進 repo**（含公司認證資料，隱私考量）。測試請用去識別化樣本。

## 6. 檔案位置

- 專案本機路徑：`c:\Users\Ryan\Documents\Antigravity folder\NCC surveillance`
- GitHub：<https://github.com/ryan94097-del/NCC-system>
- 開發歷史紀錄（舊 Python 版）：`NCC_搜尋系統開發紀錄.md`（僅供歷史參考）
