# -*- coding: utf-8 -*-
"""單筆自動核對與雙池抽樣引擎。"""
import random
import scrapers
from ncc_core import (multi_keywords, clean_cert, norm_model,
                      split_pools, rcb_code, parse_price)
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
                # 有設定價格區間但無法取得價格 → 跳過
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
        else: # MOMO 等沒有獨立型號欄位，從 title 比對
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
    """多輪搜尋：嘗試不同關鍵字直到找到結果。
    platforms = set of 'yahoo', 'momo', 'ruten'
    price_min/price_max = 價格區間篩選（None 表示不限）
    回傳 dict: keyword_used, search_rounds, candidates, confirmed
    confirmed = best matching candidate or None
    """
    if platforms is None:
        platforms = {"yahoo", "momo", "ruten"}
        
    keywords = multi_keywords(item.get("brand", ""), item.get("model", ""), item.get("product", ""), item.get("cert", ""))
    
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
    """格式化單筆結果為 dict，用於 DataFrame。
    欄位：分類, 池別, 證書編號, RCB代碼, 廠牌, 型號, 委託產品,
          結果, 賣場, 賣場NCC_ID, 精確符合, 賣場型號/名稱, 賣場連結,
          價格, 可開發票, 搜尋輪次, 搜尋關鍵字,
          Google購物, 露天, 酷澎, 蝦皮
    
    可開發票規則：
    - Yahoo / MOMO = '✅ 是'（正規電商）
    - 露天 = '⚠️ 視賣家'（非全部可開發票）
    - 蝦皮 = '⚠️ 視賣家'
    - 酷澎 = '✅ 是'（正規電商）
    """
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

def run_dual_pool(items, cert_index, year, quotas, platforms,
                  max_detail=3, delay=0.8, max_attempts=50,
                  price_min=None, price_max=None, on_status=None):
    """雙池抽樣引擎。
    
    quotas = {'LPD_CCAN': 5, 'LPD_OTHER': 10, 'TTE_CCAN': 3, 'TTE_OTHER': 8}
    platforms = set, e.g. {'yahoo', 'momo', 'ruten'}
    price_min/price_max = 價格區間篩選（None 表示不限）
    on_status(pool_key, confirmed, need, attempts, item) 為進度回呼。
    
    處理順序：LPD_CCAN → LPD_OTHER → TTE_CCAN → TTE_OTHER
    每個池隨機打亂後逐筆搜尋，湊滿配額或達嘗試上限後停止。
    
    回傳 rows list（每筆為 format_row 輸出的 dict）。
    """
    pools = split_pools(items, year)
    pool_order = ["LPD_CCAN", "LPD_OTHER", "TTE_CCAN", "TTE_OTHER"]
    rows = []
    
    for pk in pool_order:
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
                
    return rows
