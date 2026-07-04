# -*- coding: utf-8 -*-
"""NCC 清單解析與比對核心邏輯（與純 HTML 版一致，移植為 Python）。"""
import io
import re
import pandas as pd

CJK = "一-鿿"


def norm(s):
    return re.sub(r"\s+", "", str("" if s is None else s)).strip().lower()


def clean_cert(s):
    """去掉換行後附註（如「\\n(系列1)」）與前後空白。"""
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
