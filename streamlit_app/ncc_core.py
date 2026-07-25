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

def split_pools(items: list, year: str) -> dict:
    """將指定年份的產品分為 4 個池：
    {'LPD_CCAN': [...], 'LPD_OTHER': [...], 'TTE_CCAN': [...], 'TTE_OTHER': [...]}
    判斷 CCAN: cert[2:4] == 'AN'
    """
    pools = {
        'LPD_CCAN': [],
        'LPD_OTHER': [],
        'TTE_CCAN': [],
        'TTE_OTHER': []
    }
    for it in items:
        if it.get("year") != year:
            continue
        cat = it.get("cat") # "LPD" or "TTE"
        if cat not in ["LPD", "TTE"]:
            continue
        ccan_suffix = "_CCAN" if is_ccan(it.get("cert", "")) else "_OTHER"
        pool_key = f"{cat}{ccan_suffix}"
        pools[pool_key].append(it)
    return pools

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
        cat = "LPD" if "LPD" in up else ("TTE" if "TTE" in up else None)
        if not cat:
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
