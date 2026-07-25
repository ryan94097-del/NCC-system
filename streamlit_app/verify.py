# -*- coding: utf-8 -*-
"""單筆自動核對與雙池抽樣引擎。"""
import random
import scrapers
from ncc_core import (multi_keywords, clean_cert, norm_model,
                      split_pools, rcb_code, parse_price,
                      match_ncc_criteria, DISCOVER_KW_LP, DISCOVER_KW_TTE)
from scrapers import manual_links


def find_best_match(candidates, item, cert_index, price_min=None, price_max=None):
    """從候選商品中找出最佳匹配。
    規則：
    1. 價格在指定區間內（若有設定）
    2. 賣場 NCC ID 存在於 cert_index（認證清單中）
    3. 型號比對（norm_model 寬鬆比對）
    4. 精確符合（賣場 NCC ID == 搜尋產品的 cert）優先
    """
    want_model = norm_model(item.get("model", ""))
    want_cert = clean_cert(item.get("cert", "")).upper()
    best = None

    for c in candidates:
        # 價格區間篩選
        p = parse_price(c.get("price", ""))
        has_price_filter = (price_min is not None) or (price_max is not None)
        if has_price_filter:
            if p is None:
                c["_price_ok"] = False
                continue
            if price_min is not None and p < price_min:
                c["_price_ok"] = False
                continue
            if price_max is not None and p > price_max:
                c["_price_ok"] = False
                continue
        c["_price_ok"] = True

        c_ncc = clean_cert(c.get("ncc", "")).upper()
        c["_in_list"] = c_ncc in cert_index
        c["_exact"] = (c_ncc == want_cert)

        if not c["_in_list"]:
            c["_model_ok"] = False
            continue

        store = c.get("store", "")
        if store == "Yahoo":
            cm = norm_model(c.get("model", ""))
            c["_model_ok"] = bool(cm) and (cm == want_model or (want_model and want_model in cm) or (cm and cm in want_model))
        else:
            ct = norm_model(c.get("title", ""))
            c["_model_ok"] = bool(want_model) and want_model in ct

        if c["_model_ok"]:
            if best is None:
                best = c
            if c["_exact"]:
                best = c
                break

    return best


def multi_pass_verify(item, cert_index, platforms=None, max_detail=3, delay=0.8,
                      price_min=None, price_max=None):
    """多輪搜尋：嘗試不同關鍵字直到找到結果。"""
    if platforms is None:
        platforms = {"yahoo", "momo", "ruten"}

    keywords = multi_keywords(item.get("brand", ""), item.get("model", ""),
                              item.get("product", ""), item.get("cert", ""))
    all_candidates = []
    confirmed = None
    kw_used = ""
    rounds = 0

    for kw in keywords:
        rounds += 1
        kw_used = kw
        cands = []
        if "yahoo" in platforms:
            yc, _ = scrapers.search_yahoo(kw)
            cands.extend(yc)
        if "momo" in platforms:
            mc, _ = scrapers.search_momo(kw, max_detail=max_detail, delay=delay)
            cands.extend(mc)
        if "ruten" in platforms:
            rc, _ = scrapers.search_ruten(kw, max_items=5)
            cands.extend(rc)

        all_candidates.extend(cands)
        best = find_best_match(cands, item, cert_index,
                               price_min=price_min, price_max=price_max)
        if best:
            confirmed = best
            break

    return {
        "keyword_used": kw_used,
        "search_rounds": rounds,
        "candidates": all_candidates,
        "confirmed": confirmed
    }


def format_row(item, result, pool_key):
    """格式化 CCAN 池的搜尋結果為 dict。"""
    c = result.get("confirmed")
    kw = result.get("keyword_used", "")
    ml = dict(manual_links(kw))

    store = c.get("store", "") if c else ""
    invoice = ""
    if store in ["Yahoo", "MOMO", "酷澎"]:
        invoice = "✅ 是"
    elif store in ["露天", "蝦皮"]:
        invoice = "⚠️ 視賣家"

    exact_match = ""
    if c:
        exact_match = "是" if c.get("_exact") else "否"

    return {
        "分類": item.get("cat", ""),
        "池別": pool_key,
        "證書編號": item.get("cert", ""),
        "RCB代碼": rcb_code(item.get("cert", "")),
        "廠牌": item.get("brand", ""),
        "型號": item.get("model", ""),
        "委託產品": item.get("product", ""),
        "結果": "✅ 確認上架" if c else "❌ 未找到",
        "賣場": store,
        "賣場NCC_ID": c.get("ncc", "") if c else "",
        "精確符合": exact_match,
        "賣場型號/名稱": (c.get("model") or c.get("title", "")) if c else "",
        "賣場連結": c.get("link", "") if c else "",
        "價格": c.get("price", "") if c else "",
        "可開發票": invoice,
        "搜尋輪次": result.get("search_rounds", 0),
        "搜尋關鍵字": kw,
        "Google購物": ml.get("Google購物", ""),
        "露天": ml.get("露天", ""),
        "酷澎": ml.get("酷澎", ""),
        "蝦皮": ml.get("蝦皮", "")
    }


def _discover_format_row(candidate, pool_key, kw_used):
    """格式化「發現模式」（其他 RCB）的結果為 dict。"""
    store = candidate.get("store", "")
    invoice = ""
    if store in ["Yahoo", "MOMO", "酷澎"]:
        invoice = "✅ 是"
    elif store in ["露天", "蝦皮"]:
        invoice = "⚠️ 視賣家"

    ncc = clean_cert(candidate.get("ncc", ""))
    ml = dict(manual_links(kw_used))

    return {
        "分類": "LPD" if "LPD" in pool_key else "TTE",
        "池別": pool_key,
        "證書編號": ncc,
        "RCB代碼": rcb_code(ncc),
        "廠牌": "(電商發現)",
        "型號": candidate.get("model", "") or "",
        "委託產品": candidate.get("title", ""),
        "結果": "✅ 確認上架",
        "賣場": store,
        "賣場NCC_ID": ncc,
        "精確符合": "—",
        "賣場型號/名稱": candidate.get("title", ""),
        "賣場連結": candidate.get("link", ""),
        "價格": candidate.get("price", ""),
        "可開發票": invoice,
        "搜尋輪次": 0,
        "搜尋關鍵字": kw_used,
        "Google購物": ml.get("Google購物", ""),
        "露天": ml.get("露天", ""),
        "酷澎": ml.get("酷澎", ""),
        "蝦皮": ml.get("蝦皮", ""),
    }


def discover_other_rcb(year, want_cat, quota, platforms,
                       max_detail=3, delay=0.8,
                       price_min=None, price_max=None, on_status=None):
    """發現模式：用通用關鍵字在電商搜尋，找到符合條件的其他 RCB 產品。

    條件：NCC ID 年份 == year，RCB != 'AN'，分類碼符合 want_cat。
    want_cat = 'LPD' 或 'TTE'
    """
    pool_key = f"{want_cat}_OTHER"
    keywords = list(DISCOVER_KW_LP if want_cat == "LPD" else DISCOVER_KW_TTE)
    random.shuffle(keywords)

    rows = []
    seen_ncc = set()
    confirmed = 0
    kw_idx = 0

    while confirmed < quota and kw_idx < len(keywords):
        kw = keywords[kw_idx]
        kw_idx += 1

        if on_status:
            dummy_item = {"brand": "", "model": kw, "cert": "", "product": kw}
            on_status(pool_key, confirmed, quota, kw_idx, dummy_item)

        # 搜尋各平台
        all_cands = []
        if "yahoo" in platforms:
            yc, _ = scrapers.search_yahoo(kw)
            all_cands.extend(yc)
        if "momo" in platforms:
            mc, _ = scrapers.search_momo(kw, max_detail=max_detail, delay=delay)
            all_cands.extend(mc)
        if "ruten" in platforms:
            rc, _ = scrapers.search_ruten(kw, max_items=5)
            all_cands.extend(rc)

        for c in all_cands:
            if confirmed >= quota:
                break
            ncc = clean_cert(c.get("ncc", "")).upper()
            if ncc in seen_ncc:
                continue
            if not match_ncc_criteria(ncc, year, want_cat):
                continue
            # 價格篩選
            p = parse_price(c.get("price", ""))
            if (price_min is not None) or (price_max is not None):
                if p is None:
                    continue
                if price_min is not None and p < price_min:
                    continue
                if price_max is not None and p > price_max:
                    continue

            seen_ncc.add(ncc)
            rows.append(_discover_format_row(c, pool_key, kw))
            confirmed += 1

    return rows


def run_dual_pool(items, cert_index, year, quotas, platforms,
                  max_detail=3, delay=0.8, max_attempts=50,
                  price_min=None, price_max=None, on_status=None):
    """雙池抽樣引擎。

    CCAN 池：從上傳清單抽樣 → 多輪搜尋確認上架
    其他 RCB 池：發現模式 → 用通用關鍵字在電商搜尋符合條件的產品

    quotas = {'LPD_CCAN': 5, 'LPD_OTHER': 10, 'TTE_CCAN': 3, 'TTE_OTHER': 8}
    """
    pools = split_pools(items, year)
    rows = []

    # === CCAN 池：從清單抽樣搜尋 ===
    for pk in ["LPD_CCAN", "TTE_CCAN"]:
        pool_items = pools.get(pk, [])
        random.shuffle(pool_items)
        need = quotas.get(pk, 0)

        if need <= 0:
            continue

        confirmed = 0
        attempts = 0

        for it in pool_items:
            if confirmed >= need or attempts >= max_attempts:
                break

            attempts += 1
            if on_status:
                on_status(pk, confirmed, need, attempts, it)

            res = multi_pass_verify(it, cert_index, platforms=platforms,
                                    max_detail=max_detail, delay=delay,
                                    price_min=price_min, price_max=price_max)
            rows.append(format_row(it, res, pk))

            if res.get("confirmed"):
                confirmed += 1

    # === 其他 RCB 池：發現模式（不限清單）===
    for want_cat in ["LPD", "TTE"]:
        pk = f"{want_cat}_OTHER"
        need = quotas.get(pk, 0)
        if need <= 0:
            continue

        other_rows = discover_other_rcb(
            year, want_cat, need, platforms,
            max_detail=max_detail, delay=delay,
            price_min=price_min, price_max=price_max,
            on_status=on_status
        )
        rows.extend(other_rows)

    return rows
