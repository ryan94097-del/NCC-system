# -*- coding: utf-8 -*-
"""賣場自動搜尋：Yahoo購物（搜尋頁即含結構化 NCC 認證碼+型號）、
MOMO（搜尋取 i_code → 逐一抓商品頁讀 NCC字號）。其他賣場僅提供手動搜尋連結。"""
import re
import time
from urllib.parse import quote

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}
NCC_RE = r"C[CB][A-Z][A-Z]\d{2}[A-Z0-9]{6,}"

# 其他賣場的手動搜尋連結（無法自動讀 ID）
MANUAL_MARKETS = [
    ("Google購物", "https://www.google.com/search?tbm=shop&q={kw}"),
    ("露天", "https://find.ruten.com.tw/s/?q={kw}"),
    ("酷澎", "https://www.tw.coupang.com/search?q={kw}"),
    ("蝦皮", "https://shopee.tw/search?keyword={kw}"),
]


def manual_links(keyword):
    kw = quote(keyword)
    return [(name, tpl.format(kw=kw)) for name, tpl in MANUAL_MARKETS]


def _get(url, timeout=12):
    return requests.get(url, headers=UA, timeout=timeout)


def search_yahoo(keyword):
    """回傳 (candidates, search_url)。candidate = {store,ncc,model,link}。"""
    surl = "https://tw.buy.yahoo.com/search/product?p=" + quote(keyword)
    out = []
    try:
        r = _get(surl)
        if r.status_code != 200:
            return out, surl
        txt = r.text
        seen = set()
        for b in txt.split('"ec_filtertags":')[1:]:
            seg = b[:3000]
            mid = re.search(r"NCC認證碼_(" + NCC_RE + ")", seg)
            if not mid:
                continue
            mmod = re.search(r"型號_([^\"]+)", seg)
            ncc = mid.group(1)
            model = (mmod.group(1) if mmod else "").strip()
            key = (ncc, model)
            if key in seen:
                continue
            seen.add(key)
            out.append({"store": "Yahoo", "ncc": ncc, "model": model, "title": "", "link": surl})
    except Exception:
        pass
    return out, surl


def search_momo(keyword, max_detail=5, delay=0.8):
    """搜尋取前 max_detail 個 i_code，逐一抓商品頁讀 NCC字號。
    回傳 (candidates, search_url)。candidate = {store,ncc,model:'',title,link}。"""
    surl = ("https://www.momoshop.com.tw/search/searchShop.jsp?keyword="
            + quote(keyword) + "&searchType=1")
    out = []
    try:
        r = _get(surl)
        codes = list(dict.fromkeys(re.findall(r"i_code=(\d+)", r.text)))[:max_detail]
        for code in codes:
            durl = "https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code=" + code
            try:
                d = _get(durl)
                t = d.text
                mid = re.search(r"NCC字號[：:]\s*(" + NCC_RE + ")", t) or re.search(r"(" + NCC_RE + ")", t)
                if not mid:
                    continue
                mt = re.search(r'og:title" content="([^"]+)"', t)
                title = mt.group(1) if mt else ""
                out.append({"store": "MOMO", "ncc": mid.group(1), "model": "", "title": title, "link": durl})
            except Exception:
                pass
            time.sleep(delay)
    except Exception:
        pass
    return out, surl
