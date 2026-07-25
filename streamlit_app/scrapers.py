# -*- coding: utf-8 -*-
"""賣場自動搜尋：Yahoo購物（搜尋頁即含結構化 NCC 認證碼+型號）、
MOMO（搜尋取 i_code → 逐一抓商品頁讀 NCC字號）、
露天拍賣（透過解析搜尋結果取得）。其他賣場僅提供手動搜尋連結。"""
import re
import time
from urllib.parse import quote

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# 完整 14 碼 NCC ID 正規表示式
NCC_RE = r"C[CB][A-Z][A-Z]\d{2}[A-Z0-9]{2}\d{3}[0-9A-Z][TCES][0-9A-Z]"

# 其他賣場的手動搜尋連結（排除 PChome，僅保留手動）
MANUAL_MARKETS = [
    ("Google購物", "https://www.google.com/search?tbm=shop&q={kw}"),
    ("露天", "https://find.ruten.com.tw/s/?q={kw}"),
    ("酷澎", "https://www.tw.coupang.com/search?q={kw}"),
    ("蝦皮", "https://shopee.tw/search?keyword={kw}"),
]

def manual_links(keyword):
    """產生手動搜尋連結 list of (name, url)"""
    kw = quote(keyword)
    return [(name, tpl.format(kw=kw)) for name, tpl in MANUAL_MARKETS]

def _get(url, timeout=12, retries=2, headers=None):
    """HTTP GET，含重試機制"""
    req_headers = UA.copy()
    if headers:
        req_headers.update(headers)
        
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=req_headers, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            pass
        if attempt < retries:
            time.sleep(1)
    return None

def search_yahoo(keyword):
    """搜尋 Yahoo 購物中心。
    URL: https://tw.buy.yahoo.com/search/product?p={kw}
    
    從搜尋結果頁 HTML 中提取：
    1. ec_filtertags 中的 NCC認證碼_ 標籤 → NCC ID
    2. ec_filtertags 中的 型號_ 標籤 → 型號
    3. 嘗試提取商品標題與價格
    4. 嘗試提取商品連結
    
    回傳 (candidates_list, search_url)
    candidate = {'store': 'Yahoo', 'ncc': str, 'model': str, 'title': str, 'link': str, 'price': str}
    """
    surl = "https://tw.buy.yahoo.com/search/product?p=" + quote(keyword)
    out = []
    r = _get(surl)
    if not r:
        return out, surl
        
    txt = r.text
    seen = set()
    
    try:
        for b in txt.split('"ec_filtertags":')[1:]:
            seg = b[:3000]
            mid = re.search(r"NCC認證碼_(" + NCC_RE + ")", seg)
            if not mid:
                continue
            mmod = re.search(r"型號_([^\"]+)", seg)
            ncc = mid.group(1)
            model = (mmod.group(1) if mmod else "").strip()
            
            title = ""
            mtitle = re.search(r'"title":"([^"]+)"', b[:1000])
            if mtitle:
                title = mtitle.group(1)
                
            price = ""
            mprice = re.search(r'"price":(\d+)', b[:1000])
            if mprice:
                price = f"${mprice.group(1)}"
                
            mlink = re.search(r'"url":"([^"]+)"', b[:1000])
            link = mlink.group(1).replace("\\u002F", "/") if mlink else surl
            
            key = (ncc, model)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "store": "Yahoo", 
                "ncc": ncc, 
                "model": model, 
                "title": title, 
                "link": link, 
                "price": price
            })
    except Exception:
        pass
        
    return out, surl

def search_momo(keyword, max_detail=5, delay=0.8):
    """搜尋 MOMO 購物網。
    第一步：搜尋頁取得 i_code 列表
    第二步：逐一訪問商品詳情頁
    
    回傳 (candidates_list, search_url)
    """
    surl = "https://www.momoshop.com.tw/search/searchShop.jsp?keyword=" + quote(keyword) + "&searchType=1"
    out = []
    r = _get(surl)
    if not r:
        return out, surl
        
    try:
        codes = list(dict.fromkeys(re.findall(r"i_code=(\d+)", r.text)))[:max_detail]
        for code in codes:
            durl = "https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code=" + code
            try:
                d = _get(durl)
                if not d:
                    continue
                t = d.text
                mid = re.search(r"NCC字號[：:]\s*(" + NCC_RE + ")", t) or re.search(r"(" + NCC_RE + ")", t)
                if not mid:
                    continue
                ncc = mid.group(1)
                
                mt = re.search(r'og:title"\s+content="([^"]+)"', t)
                title = mt.group(1) if mt else ""
                
                mp = re.search(r'og:price:amount"\s+content="(\d+)"', t) or re.search(r'"price":\s*"(\d+)"', t)
                price = f"${mp.group(1)}" if mp else ""
                
                out.append({
                    "store": "MOMO", 
                    "ncc": ncc, 
                    "model": "", 
                    "title": title, 
                    "link": durl, 
                    "price": price
                })
            except Exception:
                pass
            time.sleep(delay)
    except Exception:
        pass
        
    return out, surl

def search_ruten(keyword, max_items=5):
    """搜尋露天拍賣。
    策略：解析頁面內嵌 JSON 或 HTML，從商品標題中用正規表示式提取 NCC ID
    
    回傳 (candidates_list, search_url)
    candidate = {'store': '露天', 'ncc': str, 'model': str, 'title': str, 'link': str, 'price': str}
    """
    surl = "https://find.ruten.com.tw/s/?q=" + quote(keyword)
    out = []
    headers = {'Referer': 'https://www.ruten.com.tw/'}
    r = _get(surl, headers=headers)
    if not r:
        return out, surl
        
    txt = r.text
    seen = set()
    
    try:
        # 嘗試從 JSON 結構抓取 (IdStr, Name, Price)
        items_json = re.findall(r'"IdStr":"([^"]+)","Name":"([^"]+)"(?:,"Price":(\d+))?', txt)
        if items_json:
            for id_str, name, price in items_json:
                mncc = re.search(r"(" + NCC_RE + ")", name)
                if mncc:
                    ncc = mncc.group(1)
                    if ncc in seen:
                        continue
                    seen.add(ncc)
                    link = f"https://www.ruten.com.tw/item/show?{id_str}"
                    p_str = f"${price}" if price else ""
                    out.append({
                        "store": "露天", 
                        "ncc": ncc, 
                        "model": "", 
                        "title": name, 
                        "link": link, 
                        "price": p_str
                    })
                    if len(out) >= max_items:
                        break
                        
        # 如果沒有從 JSON 解析到足夠商品，嘗試從 HTML 中擷取
        if not out:
            blocks = re.findall(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', txt, re.DOTALL)
            for link, inner in blocks:
                text = re.sub(r'<[^>]+>', '', inner).strip()
                mncc = re.search(r"(" + NCC_RE + ")", text)
                if mncc:
                    ncc = mncc.group(1)
                    if ncc in seen:
                        continue
                    seen.add(ncc)
                    if link.startswith('//'):
                        link = 'https:' + link
                    elif link.startswith('/'):
                        link = 'https://www.ruten.com.tw' + link
                        
                    out.append({
                        "store": "露天", 
                        "ncc": ncc, 
                        "model": "", 
                        "title": text, 
                        "link": link, 
                        "price": ""
                    })
                    if len(out) >= max_items:
                        break
    except Exception:
        pass
        
    return out, surl

if __name__ == '__main__':
    print("Test Yahoo:")
    print(search_yahoo("TP-Link 路由器"))
    print("\nTest MOMO:")
    print(search_momo("Roborock 掃地機器人", max_detail=2))
    print("\nTest Ruten:")
    print(search_ruten("TP-Link"))
