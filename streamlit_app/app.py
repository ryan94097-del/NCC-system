# -*- coding: utf-8 -*-
"""NCC 案件賣場自動核對（Streamlit Cloud 版）
上傳認證清單 → 依年份/分類隨機抽樣 → 自動到 Yahoo/MOMO 搜尋、讀取賣場 NCC ID
→ 比對清單 + 型號一致 → 湊滿需求筆數（不足自動找下一筆）。其他賣場附手動連結。
"""
import pandas as pd
import streamlit as st

from ncc_core import parse_workbook, build_cert_index
from verify import run_pool

st.set_page_config(page_title="NCC 賣場自動核對", page_icon="🔍", layout="wide")


# ── 共用密碼門檻 ──
def _correct_password():
    try:
        return st.secrets.get("app_password", "ncc2026")
    except Exception:
        return "ncc2026"


def gate():
    if st.session_state.get("auth"):
        return True
    st.title("🔒 NCC 賣場自動核對")
    pw = st.text_input("請輸入共用密碼", type="password")
    if pw:
        if pw == _correct_password():
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("密碼錯誤，請重試。")
    st.caption("預設密碼 ncc2026，可於 Streamlit Cloud 的 Secrets 以 app_password 覆蓋。")
    return False


def run_search(items, cert_index, year, need_map, use_yahoo, use_momo,
               max_detail, delay, max_attempts):
    """呼叫純函式 run_pool，並以回呼更新 Streamlit 進度。"""
    total_need = max(sum(need_map.values()), 1)
    prog = st.progress(0.0)
    status = st.empty()
    counter = {"n": 0}

    def on_status(cat, confirmed, need, attempts, it):
        counter["n"] = confirmed
        status.markdown("🔎 **[%s]** 搜尋中（已確認 %d/%d，已查 %d 筆）：`%s %s`"
                        % (cat, confirmed, need, attempts, it["brand"], it["model"]))
        prog.progress(min(confirmed / total_need, 1.0))

    rows = run_pool(items, cert_index, year, need_map, use_yahoo=use_yahoo,
                    use_momo=use_momo, max_detail=max_detail, delay=delay,
                    max_attempts=max_attempts, on_status=on_status)
    prog.progress(1.0)
    n_ok = sum(1 for r in rows if r["結果"].startswith("✅"))
    status.markdown("✅ 完成：共確認 **%d** 筆上架（查了 %d 筆）。" % (n_ok, len(rows)))
    return rows


def main():
    if not gate():
        return

    st.title("🔍 NCC 案件賣場自動核對")
    st.caption("Yahoo購物 / MOMO 自動讀取賣場 NCC ID 並比對；酷澎/蝦皮/Google/露天 附手動連結。")

    with st.sidebar:
        st.header("⚙️ 設定")
        up = st.file_uploader("上傳認證清單（Excel）", type=["xlsx", "xls"])
        year = st.selectbox("目標年份（證號年份碼）",
                            [str(y).zfill(2) for y in range(14, 31)], index=12)
        st.subheader("各分類需求筆數")
        lpd_n = st.number_input("LPD 需要幾筆", 1, 200, 5)
        tte_n = st.number_input("TTE 需要幾筆", 1, 200, 3)
        st.subheader("賣場（自動）")
        use_yahoo = st.checkbox("Yahoo購物（快、準）", value=True)
        use_momo = st.checkbox("MOMO（逐頁抓，較慢）", value=True)
        max_detail = st.slider("MOMO 每筆最多抓幾個商品頁", 1, 8, 3)
        st.subheader("防封鎖")
        delay = st.slider("請求間隔（秒）", 0.3, 3.0, 0.8, 0.1)
        max_attempts = st.slider("每分類最多嘗試幾筆（湊不滿就停）", 5, 200, 30)

    if up is None:
        st.info("👈 請先於左側上傳認證清單 Excel。")
        st.markdown(
            "**運作方式**：系統會在該年份的 LPD / TTE 清單中**隨機抽選**，逐筆到 Yahoo/MOMO "
            "搜尋並讀取賣場標示的 NCC 認證碼，若**該 ID 在你的清單且型號一致**即算「確認上架」；"
            "**湊不滿需求筆數會自動往下一筆找**，直到補齊或達嘗試上限。"
        )
        return

    try:
        items, report = parse_workbook(up.getvalue())
    except Exception as e:
        st.error("解析失敗：%s" % e)
        return

    cert_index = build_cert_index(items)
    for line in report:
        st.write(line)

    by_year = [it for it in items if it["year"] == year]
    n_lpd = sum(1 for it in by_year if it["cat"] == "LPD")
    n_tte = sum(1 for it in by_year if it["cat"] == "TTE")
    c1, c2, c3 = st.columns(3)
    c1.metric("清單總筆數", len(items))
    c2.metric("20%s LPD" % year, n_lpd)
    c3.metric("20%s TTE" % year, n_tte)

    if st.button("🚀 開始自動搜尋核對", type="primary", use_container_width=True):
        if not (use_yahoo or use_momo):
            st.warning("請至少勾選一個自動賣場（Yahoo 或 MOMO）。")
            return
        with st.spinner("自動搜尋中，請稍候…"):
            rows = run_search(items, cert_index, year,
                              {"LPD": lpd_n, "TTE": tte_n},
                              use_yahoo, use_momo, max_detail, delay, max_attempts)
        st.session_state["rows"] = rows

    rows = st.session_state.get("rows")
    if rows:
        df = pd.DataFrame(rows)
        n_ok = sum(1 for r in rows if r["結果"].startswith("✅"))
        st.subheader("📊 結果（確認上架 %d / 共查 %d 筆）" % (n_ok, len(rows)))
        st.dataframe(
            df,
            use_container_width=True, hide_index=True,
            column_config={
                "賣場連結": st.column_config.LinkColumn("賣場連結", display_text="前往"),
                "Google購物": st.column_config.LinkColumn("Google", display_text="搜尋"),
                "露天": st.column_config.LinkColumn("露天", display_text="搜尋"),
                "酷澎": st.column_config.LinkColumn("酷澎", display_text="搜尋"),
                "蝦皮": st.column_config.LinkColumn("蝦皮", display_text="搜尋"),
            },
        )
        csv = "﻿" + df.to_csv(index=False)
        st.download_button("📥 下載結果 CSV", data=csv.encode("utf-8"),
                           file_name="NCC自動核對結果_20%s.csv" % year, mime="text/csv")


if __name__ == "__main__":
    main()
