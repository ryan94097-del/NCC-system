# 架構與資料結構（ARCHITECTURE）

## 1. 整體架構

單一 `NCC核對工具.html`，全部在瀏覽器內執行，無網路請求（除使用者手動點開的搜尋連結）。

```
[使用者上傳 Excel/CSV]
        ↓  (SheetJS，內嵌)
[解析：抓第2列表頭 → 分流 LPD/TTE → 清洗雜訊列]
        ↓
[篩選：年份碼過濾 + 去重]
        ↓
[渲染核對工作表：每列 = 一筆產品 + 六賣場一鍵搜尋連結 + 狀態/備註/價格/截圖欄]
        ↓
[匯出：CSV (utf-8-sig) / Excel]
```

建議模組切分（皆在同一 HTML 內）：`parser`（Excel）、`filter`（年份/去重）、`keyword`（關鍵字生成）、`linkgen`（賣場 URL）、`worksheet`（UI/狀態）、`exporter`（匯出）。

## 2. Excel 資料結構（實測，以此為準）

檔案：`RCB工服委託登錄表_TUV_2026.xlsx`

- 分頁：`LPD型式認證列表`、`TTE型式認證列表`、`NCC簡易符合性聲明列表`、`平台登錄&標籤授權&保密設定`、`委外發證列表`、`TRT Contract Date`。
  **目前只處理 LPD / TTE。**
- **真正表頭在第 2 列**（row index 1）；第 1 列是大標題，要跳過。
- 關鍵欄位：
  - `證書編號` = NCC ID，如 `CCAN26LP0010T1`（**注意：`委託編號`（如 114027667）不是 NCC ID**）
  - `廠牌`、`型號`、`委託產品`
- **年份碼 = 證書編號第 5–6 碼**：`CCAN`**`26`**`LP0010T1` → `26` → 2026 年。
- 資料量參考：LPD 約 2,023 筆有證號（2026 年 153 筆）；TTE 約 47 筆（2026 年 4 筆）。

### 必須清洗的資料坑

- 證號夾雜換行：`CCAN264G0021T0\n(系列1)` → 取年份/顯示前要 `trim` 掉換行與括號。
- 年份分隔列：整列只有一個數字（如 `2018`）→ 丟棄。
- `NCC 請款` 彙總列：證書編號為空 → 丟棄。
- 只保留證書編號以 `CC` 開頭的有效列。
- 很多型號是通用短字串（`700`、`X8`、`SBP`、`P232`）→ 搜尋雜訊大，需搭配廠牌/產品類別詞。

## 3. 關鍵字策略

- 預設關鍵字 = `廠牌 + 空格 + 型號`。
- 型號長度 < 4 或為純數字/通用字時，追加產品類別詞（取自 `委託產品` 的中文名）。
- 保留原始型號與廠牌欄，讓使用者可自行微調關鍵字。

## 4. 六大賣場搜尋 URL 樣式（`{kw}` 需 `encodeURIComponent`）

| 賣場 | 搜尋 URL 樣式 |
|---|---|
| MOMO | `https://www.momoshop.com.tw/search/searchShop.jsp?keyword={kw}&searchType=1` |
| Yahoo 購物 | `https://tw.buy.yahoo.com/search/product?p={kw}` |
| Google 購物 | `https://www.google.com/search?tbm=shop&q={kw}` |
| 露天 | `https://find.ruten.com.tw/s/?q={kw}` |
| 酷澎 Coupang | `https://www.tw.coupang.com/search?q={kw}`（建置時再驗證最新路徑） |
| 蝦皮 Shopee | `https://shopee.tw/search?keyword={kw}` |

> ⚠️ 電商搜尋路徑偶爾改版，建置時逐一開連結驗證一次。**PChome 一律排除。**

## 5. 匯出格式

欄位建議：`分類, 證書編號, 廠牌, 型號, 委託產品, 核對狀態, 賣家, 價格, 備註, (截圖), 各賣場搜尋連結`。
CSV 用 `utf-8-sig` 確保 Excel 開啟不亂碼；Excel 匯出可用內嵌 SheetJS 產生 `.xlsx`。
