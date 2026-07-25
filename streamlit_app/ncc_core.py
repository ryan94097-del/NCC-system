# -*- coding: utf-8 -*-
"""NCC 清單解析與分組核心。"""
import io
import re
import pandas as pd

CJK = "一-鿿"


def parse_price(price_str):
    """將價格字串轉為數字。如 '$1,290' → 1290, '' → None"""
    if not price_str:
        return None
    digits = re.sub(r"[^\d]", "", str(price_str))
    return int(digits) if digits else None

def norm(s):
    return re.sub(r"\s+", "", str("" if s is None else s)).strip().lower()

def clean_cert(s):
    """去掉換行後附註（如「\n(系列1)」）與前後空白。"""
    return re.split(r"[\r\n]", str("" if s is None else s))[0].strip()

def year_of(cert):
    c = clean_cert(cert).upper()
    return c[4:6] if len(c) >= 6 and c.startswith("CC") else ""

def norm_model(s):
    """寬鬆型號比對：僅保留中英數並轉大寫（AX-100 / AX 100 / ax100 視為相同）。"""
    return re.sub(r"[^0-9A-Za-z" + CJK + "]", "", str("" if s is None else s)).upper()

def is_generic_model(m):
    m = str(m or "").strip()
    return len(m) < 4 or m.isdigit()

def chinese_of(s):
    m = re.findall(r"[" + CJK + r"][" + CJK + r"0-9A-Za-z]*", str(s or ""))
    return "".join(m)

def default_keyword(brand, model, product):
    base = (str(brand or "").strip() + " " + str(model or "").strip()).strip()
    if is_generic_model(model):
        cat = chinese_of(product)
        if cat:
            base = (base + " " + cat).strip()
    return base

def rcb_code(cert: str) -> str:
    """取得 RCB 代碼（第 3-4 碼）。如 'CCAN25LP0010T3' → 'AN'"""
    c = clean_cert(cert).upper()
    return c[2:4] if len(c) >= 4 and c.startswith("CC") else ""

def is_ccan(cert: str) -> bool:
    """判斷是否為 CCAN（RCB 代碼 = 'AN'）"""
    return rcb_code(cert) == "AN"

def category_code(cert: str) -> str:
    """取得設備分類碼（第 7-8 碼）。如 'CCAN25LP0010T3' → 'LP'"""
    c = clean_cert(cert).upper()
    return c[6:8] if len(c) >= 8 else ""

# 其他 RCB 發現模式：通用搜尋關鍵字（用來在電商廣泛搜尋 RF/通訊產品）
DISCOVER_KW_LP = [
    "無線路由器", "WiFi 路由器", "藍牙耳機", "藍牙喇叭",
    "無線網卡", "WiFi 分享器", "無線滑鼠", "無線鍵盤",
    "無線充電器", "行車記錄器", "智慧手錶", "無線AP",
    "WiFi 7 路由器", "WiFi 6 路由器", "物聯網 IoT",
    "智慧家電 WiFi", "無線監視器", "無線門鈴",
]
DISCOVER_KW_TTE = [
    "5G手機", "4G手機", "智慧型手機", "平板電腦 LTE",
    "4G路由器", "5G路由器", "行動WiFi", "行動熱點",
    "衛星電話", "對講機",
]
DISCOVER_KW_DOC = [
    "無線螢幕分享器", "藍牙發射器", "RF發射器", "無線耳機線",
    "無線控制器", "感應器"
]

# LP 分類碼對照
LP_CODES = {"LP"}   # 低功率射頻
TTE_CODES = {"4G", "3G", "5G", "TE"}  # 電信終端
DOC_CODES = {"DO", "DC"}  # 符合性聲明

def match_ncc_criteria(ncc_id: str, year: str, want_cat: str) -> bool:
    """判斷一個 NCC ID 是否符合「其他 RCB」發現條件：
    1. 年份碼（第 5-6 碼）== year
    2. RCB 代碼（第 3-4 碼）!= 'AN'（非 CCAN）
    3. 分類碼（第 7-8 碼）符合 want_cat ('LPD', 'TTE', 或 'DOC')
    """
    c = clean_cert(ncc_id).upper()
    if len(c) < 8 or not c.startswith("CC"):
        return False
    # 年份
    if c[4:6] != year:
        return False
    # 非 CCAN
    if c[2:4] == "AN":
        return False
    # 分類
    cat_code = c[6:8]
    if want_cat == "LPD":
        return cat_code in LP_CODES
    elif want_cat == "TTE":
        return cat_code in TTE_CODES
    elif want_cat == "DOC":
        return cat_code in DOC_CODES or (cat_code not in LP_CODES and cat_code not in TTE_CODES)
    return False

def split_pools(items: list, year: str) -> dict:
    """將指定年份的產品分為 6 個池（LP/TTE/DOC × CCAN/OTHER）。
    判斷 CCAN: cert[2:4] == 'AN'
    """
    pools = {
        'LPD_CCAN': [], 'LPD_OTHER': [],
        'TTE_CCAN': [], 'TTE_OTHER': [],
        'DOC_CCAN': [], 'DOC_OTHER': [],
    }
    for it in items:
        if it.get("year") != year:
            continue
        cat = it.get("cat")  # "LPD", "TTE", "DOC"
        if cat not in ["LPD", "TTE", "DOC"]:
            continue
        ccan_suffix = "_CCAN" if is_ccan(it.get("cert", "")) else "_OTHER"
        pools[cat + ccan_suffix].append(it)
    return pools


def calc_quotas(items: list, year: str) -> dict:
    """根據 NCC 抽驗規定自動計算各池抽樣配額。

    規則：
    1. 各分類每年抽驗件數 ≥ 當年度審驗合格總件數的 5%
    2. LP（低功率射頻）最低 2 件，且須涵蓋不同驗證機構
    3. 若該年份/該分類 0 件則不需抽
    4. LP / TTE / DOC 分開計算

    回傳 dict:
      quotas: {'LPD_CCAN': n, 'LPD_OTHER': n, 'TTE_CCAN': n, 'TTE_OTHER': n,
               'DOC_CCAN': n, 'DOC_OTHER': n}
      stats: {'lp_total': n, 'tte_total': n, 'doc_total': n,
              'lp_5pct': n, 'tte_5pct': n, 'doc_5pct': n,
              'lp_quota': n, 'tte_quota': n, 'doc_quota': n}
    """
    import math
    pools = split_pools(items, year)

    def _calc(cat_prefix, min_total=0):
        """計算單一分類的配額。"""
        ccan_count = len(pools.get(f"{cat_prefix}_CCAN", []))
        other_count = len(pools.get(f"{cat_prefix}_OTHER", []))
        total = ccan_count + other_count
        pct5 = math.ceil(total * 0.05) if total > 0 else 0
        quota = max(pct5, min_total) if total > 0 else 0

        if quota <= 0:
            return 0, 0, total, pct5, quota

        # 分配 CCAN / OTHER
        # 規則：須涵蓋不同驗證機構 → 至少 1 件 OTHER（發現模式）
        if quota >= 2:
            q_other = max(1, math.ceil(quota * 0.2))  # 至少 20% 給 OTHER，最少 1
            q_ccan = quota - q_other
        else:
            # quota == 1，全給 CCAN
            q_ccan = 1
            q_other = 0

        return q_ccan, q_other, total, pct5, quota

    lp_ccan, lp_other, lp_total, lp_5pct, lp_quota = _calc("LPD", min_total=2)
    tte_ccan, tte_other, tte_total, tte_5pct, tte_quota = _calc("TTE", min_total=0)
    doc_ccan, doc_other, doc_total, doc_5pct, doc_quota = _calc("DOC", min_total=0)

    return {
        "quotas": {
            "LPD_CCAN": lp_ccan, "LPD_OTHER": lp_other,
            "TTE_CCAN": tte_ccan, "TTE_OTHER": tte_other,
            "DOC_CCAN": doc_ccan, "DOC_OTHER": doc_other,
        },
        "stats": {
            "lp_total": lp_total, "tte_total": tte_total, "doc_total": doc_total,
            "lp_5pct": lp_5pct, "tte_5pct": tte_5pct, "doc_5pct": doc_5pct,
            "lp_quota": lp_quota, "tte_quota": tte_quota, "doc_quota": doc_quota,
        }
    }

def multi_keywords(brand, model, product, cert) -> list:
    """產生多層搜尋關鍵字列表（NCC ID 優先）
    第1輪: NCC ID 直搜（最精準，找有標示認證碼的商品）
    第2輪: 品牌+型號（補充搜尋）
    第3輪: 品牌+型號+產品類別中文詞（僅當型號短/通用時）
    """
    keywords = []
    # 第 1 輪：NCC ID 直搜
    c = clean_cert(cert)
    if c:
        keywords.append(c)
    # 第 2 輪：品牌 + 型號
    base = (str(brand or "").strip() + " " + str(model or "").strip()).strip()
    if base and base not in keywords:
        keywords.append(base)
    # 第 3 輪：品牌 + 型號 + 產品類別（短型號補強）
    if is_generic_model(model):
        cat = chinese_of(product)
        if cat and base:
            kw3 = (base + " " + cat).strip()
            if kw3 not in keywords:
                keywords.append(kw3)
        
    return keywords

def parse_workbook(file_bytes):
    """讀取 Excel，抓第 2 列表頭、分流 LPD/TTE、清洗雜訊列。回傳 items list。"""
    xl = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    items = []
    report = []
    for sn in xl.sheet_names:
        up = sn.upper()
        if "LPD" in up or "LP" in up:
            cat = "LPD"
        elif "TTE" in up:
            cat = "TTE"
        elif "DOC" in up:
            cat = "DOC"
        else:
            continue
        raw = pd.read_excel(xl, sheet_name=sn, header=None, dtype=str)
        hidx = None
        for i in range(min(len(raw), 15)):
            vals = [norm(v) for v in raw.iloc[i].tolist() if pd.notna(v)]
            if norm("證書編號") in vals and norm("型號") in vals:
                hidx = i
                break
        if hidx is None:
            report.append("⚠️ 分頁「%s」找不到表頭，略過" % sn)
            continue
        header = [norm(v) for v in raw.iloc[hidx].tolist()]

        def col(name):
            n = norm(name)
            return header.index(n) if n in header else -1

        cC, cM, cB, cP = col("證書編號"), col("型號"), col("廠牌"), col("委託產品")
        if cC < 0 or cM < 0:
            report.append("⚠️ 分頁「%s」缺欄位，略過" % sn)
            continue
        kept = 0
        for r in range(hidx + 1, len(raw)):
            row = raw.iloc[r].tolist()
            cert = clean_cert(row[cC])
            if not cert or not cert.upper().startswith("CC"):
                continue
            model = str(row[cM]).strip() if pd.notna(row[cM]) else ""
            if not model or model.lower() == "nan":
                continue
            brand = str(row[cB]).strip() if cB >= 0 and pd.notna(row[cB]) else ""
            product = str(row[cP]).strip() if cP >= 0 and pd.notna(row[cP]) else ""
            items.append({"cat": cat, "cert": cert, "brand": brand,
                          "model": model, "product": product, "year": year_of(cert)})
            kept += 1
        report.append("✅ 分頁「%s」(%s)：%d 筆" % (sn, cat, kept))

    seen, out = set(), []
    for it in items:
        k = (it["cat"], it["cert"], it["model"])
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out, report

def build_cert_index(items):
    idx = {}
    for it in items:
        idx.setdefault(clean_cert(it["cert"]).upper(), []).append(it)
    return idx
