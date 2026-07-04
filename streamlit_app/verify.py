# -*- coding: utf-8 -*-
"""單筆自動核對：搜尋賣場 → 讀到的 NCC ID 是否在清單 + 型號是否一致。"""
import random

import scrapers
from ncc_core import default_keyword, clean_cert, norm_model
from scrapers import manual_links


def verify_item(item, cert_index, use_yahoo=True, use_momo=True, max_detail=5, delay=0.8):
    """回傳 dict：keyword、candidates（含判定）、confirmed（最佳確認候選或 None）。
    確認標準：賣場讀到的 NCC ID 存在清單任一筆，且型號與所搜尋的品項一致。"""
    kw = default_keyword(item["brand"], item["model"], item["product"])
    cands = []
    yurl = murl = None
    if use_yahoo:
        yc, yurl = scrapers.search_yahoo(kw)
        cands += yc
    if use_momo:
        mc, murl = scrapers.search_momo(kw, max_detail=max_detail, delay=delay)
        cands += mc

    want = norm_model(item["model"])
    self_cert = clean_cert(item["cert"]).upper()
    best = None
    for c in cands:
        cid = clean_cert(c["ncc"]).upper()
        c["_in_list"] = cid in cert_index
        c["_exact"] = (cid == self_cert)
        if not c["_in_list"]:
            c["_model_ok"] = False
            continue
        if c["store"] == "Yahoo":
            cm = norm_model(c.get("model", ""))
            c["_model_ok"] = bool(cm) and (cm == want or (want and want in cm) or (cm and cm in want))
        else:  # MOMO：無獨立型號欄，用商品名稱含型號判定
            ct = norm_model(c.get("title", ""))
            c["_model_ok"] = bool(want) and want in ct
        if c["_model_ok"] and best is None:
            best = c
        if c["_model_ok"] and c["_exact"]:
            best = c
            break
    return {"keyword": kw, "candidates": cands, "confirmed": best,
            "yahoo_url": yurl, "momo_url": murl}


def _row(it, res):
    c = res["confirmed"]
    ml = dict(manual_links(res["keyword"]))
    return {
        "分類": it["cat"], "證書編號": it["cert"], "廠牌": it["brand"],
        "型號": it["model"], "委託產品": it["product"],
        "結果": "✅ 確認上架" if c else "❌ 未找到",
        "賣場": c["store"] if c else "",
        "賣場NCC ID": c["ncc"] if c else "",
        "精確符合": ("是" if (c and c["_exact"]) else ("否" if c else "")),
        "賣場型號/名稱": (c.get("model") or c.get("title", "")) if c else "",
        "賣場連結": c["link"] if c else "",
        "Google購物": ml.get("Google購物", ""), "露天": ml.get("露天", ""),
        "酷澎": ml.get("酷澎", ""), "蝦皮": ml.get("蝦皮", ""),
        "搜尋關鍵字": res["keyword"],
    }


def run_pool(items, cert_index, year, need_map, use_yahoo=True, use_momo=True,
             max_detail=3, delay=0.8, max_attempts=30, on_status=None):
    """依年份/分類隨機抽樣並自動核對，湊滿 need_map 指定筆數（不足自動找下一筆）。
    on_status(cat, confirmed, need, attempts, item) 為進度回呼。回傳 rows list。純函式。"""
    by_cat = {}
    for it in items:
        if it["year"] == year:
            by_cat.setdefault(it["cat"], []).append(it)

    rows = []
    for cat in ["LPD", "TTE"]:
        pool = list(by_cat.get(cat, []))
        random.shuffle(pool)
        need = need_map.get(cat, 0)
        if need <= 0:
            continue
        confirmed = attempts = 0
        for it in pool:
            if confirmed >= need or attempts >= max_attempts:
                break
            attempts += 1
            if on_status:
                on_status(cat, confirmed, need, attempts, it)
            res = verify_item(it, cert_index, use_yahoo=use_yahoo, use_momo=use_momo,
                              max_detail=max_detail, delay=delay)
            rows.append(_row(it, res))
            if res["confirmed"]:
                confirmed += 1
    return rows
