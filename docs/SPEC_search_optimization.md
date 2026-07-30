# 實作規格：搜尋優化（交給 Antigravity 實作）

對象檔案：`streamlit_app/ncc_core.py`、`streamlit_app/verify.py`、`streamlit_app/app.py`
撰寫日期：2026-07-30　狀態：待實作

## 背景（現況，勿重做）
以下已存在，**不要重複實作**：
- 找不到自動跳下一筆（`run_dual_pool` 的 fill-to-count）、多輪關鍵字（`multi_keywords`：NCC ID → 品牌+型號 → +產品類別）、多平台（Yahoo/MOMO/露天）、價格區間篩選（`find_best_match` + app.py `price_min/max`）、結果✅置頂排序。

本規格只新增 **3 項**：A 消費性優先（效率模式，**預設開**）、B 產品名稱搜尋輪、C（選用）跳過極端非消費品。

---

## A. 效率模式：優先搜尋消費性產品（預設開）

**目的**：CCAN 池目前是 `random.shuffle` 純隨機，會浪費嘗試在工業/車用/B2B（電商幾乎不上架）品項。改為「優先搜尋較可能上架的消費性產品」，減少白搜。

### A-1. `ncc_core.py` 新增消費性評分

```python
# 消費性關鍵字（中英），分數 = 命中正詞數 - 命中負詞數，越高越像消費品
CONSUMER_POS = [
    "耳機","耳麥","藍牙","藍芽","喇叭","音箱","音響","滑鼠","鍵盤","路由器","分享器","網卡",
    "手錶","手環","穿戴","充電器","充電座","行動電源","行車記錄","記錄器","監視器","攝影機","門鈴","門鎖",
    "掃地機","吸塵器","體重","體脂","血壓","血氧","玩具","遙控","空拍","無人機","相機","平板","手機",
    "電視棒","電視盒","遊戲","手把","麥克風","檯燈","插座","延長線","溫濕度","翻譯機","按摩","咖啡機",
    "電子鍋","風扇","除濕","加濕","智慧家","路由","無線ap",
    "headphone","earbud","earphone","headset","speaker","mouse","keyboard","router","watch","band",
    "camera","tablet","phone","charger","doorbell","robot","drone","gamepad",
]
CONSUMER_NEG = [
    "模組","module","車用","車載","automotive","工業","industrial","閘道","gateway","醫療","medical",
    "伺服器","server","基地台","basestation","天線","antenna","讀卡","pos","嵌入","embedded","oem",
    "儀器","儀表","控制器","controller","交換器","企業","enterprise","機房","機架","rack","終端機","kiosk",
    "評估板","開發板","evaluation","電表","電錶","感測模組","reference","referencedesign",
]

def consumer_score(brand, model, product) -> int:
    """消費性分數：越高越像一般消費性產品（越可能在電商上架）。"""
    text = norm("%s %s %s" % (brand or "", model or "", product or ""))  # norm() 會轉小寫+去空白
    pos = sum(1 for k in CONSUMER_POS if k.replace(" ", "") in text)
    neg = sum(1 for k in CONSUMER_NEG if k.replace(" ", "") in text)
    return pos - neg
```
註：`norm()` 已存在（轉小寫、去所有空白），關鍵字比對前也要去空白，多字英文詞（如 base station）在清單裡直接寫成無空白 `basestation`。

### A-2. `verify.py` — `run_dual_pool` 增加 `efficiency_mode` 參數

- 簽名新增：`def run_dual_pool(..., efficiency_mode=True, ...):`（**預設 True**）
- 匯入：`from ncc_core import (... , consumer_score)`
- CCAN 池排序處，把現有的：
  ```python
  pool_items = pools.get(pk, [])
  random.shuffle(pool_items)
  ```
  改為：
  ```python
  pool_items = list(pools.get(pk, []))
  random.shuffle(pool_items)                      # 先隨機（同分時的亂序 tie-break，保留可辯護性）
  if efficiency_mode:
      pool_items.sort(                            # stable sort：同分維持上面的隨機順序
          key=lambda it: consumer_score(it.get("brand",""), it.get("model",""), it.get("product","")),
          reverse=True,
      )
  ```
- **重點**：即使效率模式開，也**先隨機再穩定排序**，讓同分項目仍是隨機順序（抽驗可辯護）。**不要**在效率模式下硬跳過任何品項（除非做 C）。

### A-3. `app.py` — 側邊欄開關（預設開）

在執行設定區加：
```python
efficiency_mode = st.checkbox(
    "⚡ 效率模式：優先搜尋消費性產品（預設開）", value=True,
    help="開：CCAN 池優先搜較可能上架的消費性產品，減少白搜。"
         "關：維持純隨機（法規抽驗更好辯護）。同分一律隨機排序。",
)
```
並把 `efficiency_mode=efficiency_mode` 傳進 `run_dual_pool(...)`。

---

## B. 新增「產品名稱」搜尋輪（`ncc_core.py` `multi_keywords`）

用委託產品全名再搜一輪，抓到「用型號找不到、但用品名找得到」的商品（仍靠 NCC ID 把關，不會誤判）。

在 `multi_keywords` 目前第 3 輪之後、`return keywords` 之前加：
```python
    # 第 4 輪：品牌 + 委託產品全名（品名搜尋）
    p = str(product or "").strip()
    if p:
        kw4 = (str(brand or "").strip() + " " + p).strip()
        if kw4 and kw4 not in keywords:
            keywords.append(kw4)
```
註：放在最後（較不精準的輪次墊底），前面精準輪次命中就會提早 break，不影響速度。

---

## C.（選用）效率模式下跳過極端非消費品

若想更省嘗試次數：在 A-2 排序後，效率模式下可**跳過 `consumer_score <= -3` 的品項**（明顯工業/B2B）。
- 風險：可能漏掉少數確實有上架者 → **預設不啟用**；若要做，另加一個側邊欄勾選「跳過明顯非消費品」預設關。

---

## 測試（實作後請跑）
1. `cd streamlit_app && python -m py_compile app.py ncc_core.py scrapers.py verify.py`
2. 單元：`consumer_score("Sony","WH-1000","藍牙耳機") > 0`；`consumer_score("Acme","MOD-1","車用通訊模組") < 0`。
3. `run_dual_pool(..., efficiency_mode=True)` 與 `False` 各跑一次 `sample/NCC_測試樣本.xlsx`，確認無例外、效率模式時消費性品項排前面。
4. `streamlit.testing.v1.AppTest` 冒煙：授權後新勾選存在、無 exception。

## 注意（抽驗可辯護性）
效率模式**預設開**（使用者指定）。因為 fill-to-count 本就使最終樣本＝「找得到的品項」，排序主要是**效率**提升；只有「可找到數 > 配額」時才影響最終選誰。已用「先隨機再穩定排序、同分隨機、不硬跳過」把偏差降到最低。需要純隨機以利稽核時，關掉開關即可。
