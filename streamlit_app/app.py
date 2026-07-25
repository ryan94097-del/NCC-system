import pandas as pd
import streamlit as st
from ncc_core import parse_workbook, build_cert_index, split_pools
from verify import run_dual_pool

st.set_page_config(page_title="NCC 電商市場監督搜尋引擎", page_icon="🔍", layout="wide")

# === 自訂 CSS（深色科技風）===
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap');

/* 全域字型 */
html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans TC', sans-serif;
}

/* 標題漸層 */
h1 {
    background: linear-gradient(135deg, #6366f1, #a855f7, #ec4899);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
}

/* Metric 卡片玻璃擬態 */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    backdrop-filter: blur(10px);
    padding: 1rem;
    transition: transform 0.2s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    border-color: rgba(99,102,241,0.4);
}

/* 主按鈕漸層 */
button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
}
button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(99,102,241,0.4) !important;
}

/* 側邊欄美化 */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e1b4b 0%, #0f172a 100%) !important;
    border-right: 1px solid rgba(99,102,241,0.2);
}

/* 分隔線 */
hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(99,102,241,0.3), transparent);
    margin: 1.5rem 0;
}

/* 表格美化 */
.dataframe {
    border-radius: 8px;
    overflow: hidden;
}

/* 進度條 */
.stProgress > div > div {
    background: linear-gradient(90deg, #6366f1, #a855f7) !important;
}

/* 成功/錯誤訊息圓角 */
.stAlert {
    border-radius: 10px;
}
</style>
"""

def inject_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# === 密碼門檻 ===
def _correct_password():
    try:
        return st.secrets.get("app_password", "ncc2026")
    except Exception:
        return "ncc2026"

def gate():
    if st.session_state.get("auth"):
        return True
    inject_css()
    st.markdown("""<div style='text-align:center; padding: 3rem 0;'>
        <h1 style='font-size:2.5rem;'>🔍 NCC 電商市場監督搜尋引擎</h1>
        <p style='color:#94a3b8; font-size:1.1rem;'>National Communications Commission — 市場抽驗搜尋工具</p>
    </div>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        pw = st.text_input("🔐 請輸入共用密碼", type="password", placeholder="輸入密碼後按 Enter")
        if pw:
            if pw == _correct_password():
                st.session_state["auth"] = True
                st.rerun()
            else:
                st.error("❌ 密碼錯誤，請重試。")
    return False

# === 主頁面 ===
def main():
    if not gate():
        return
    inject_css()
    
    # 標題區
    st.markdown("""<h1 style='font-size:2rem; margin-bottom:0;'>🔍 NCC 電商市場監督搜尋引擎</h1>
    <p style='color:#94a3b8;'>上傳認證清單 → CCAN/其他 RCB 雙池抽樣 → Yahoo/MOMO/露天 自動搜尋 → 整理可購買商品</p>""", unsafe_allow_html=True)
    st.markdown("---")
    
    # === 側邊欄 ===
    with st.sidebar:
        st.markdown("### ⚙️ 搜尋設定")
        
        # 上傳
        up = st.file_uploader("📁 上傳認證清單 Excel", type=["xlsx", "xls"])
        
        st.markdown("---")
        
        # 年份
        year = st.selectbox("📅 目標年份", ["25", "24"], format_func=lambda y: f"20{y}年")
        
        st.markdown("---")
        
        # CCAN 雙池配額
        st.markdown("### 🎯 抽樣配額")
        st.caption("CCAN = 自家驗證機構 (AN) / 其他 = 其餘 RCB")
        
        st.markdown("**📡 LP（低功率射頻）**")
        col1, col2 = st.columns(2)
        lpd_ccan = col1.number_input("CCAN", 0, 200, 5, key="lpd_ccan")
        lpd_other = col2.number_input("其他RCB", 0, 200, 10, key="lpd_other")
        
        st.markdown("**📱 TTE（電信終端）**")
        col3, col4 = st.columns(2)
        tte_ccan = col3.number_input("CCAN", 0, 200, 3, key="tte_ccan")
        tte_other = col4.number_input("其他RCB", 0, 200, 8, key="tte_other")
        
        st.markdown("---")
        
        # 平台選擇
        st.markdown("### 🏪 搜尋平台")
        use_yahoo = st.checkbox("Yahoo購物 🟢 (快速、準確)", value=True)
        use_momo = st.checkbox("MOMO購物 🟡 (較慢、需逐頁)", value=True)
        use_ruten = st.checkbox("露天拍賣 🟡 (補充來源)", value=False)
        
        st.markdown("---")
        
        # 價格區間篩選
        st.markdown("### 💰 價格區間")
        st.caption("只保留價格在此區間內的商品（0 = 不限）")
        pc1, pc2 = st.columns(2)
        price_min_val = pc1.number_input("最低 (NT$)", 0, 999999, 0, step=100, key="price_min")
        price_max_val = pc2.number_input("最高 (NT$)", 0, 999999, 0, step=100, key="price_max")
        
        st.markdown("---")
        
        # 進階設定（折疊）
        with st.expander("⚡ 進階設定"):
            max_detail = st.slider("MOMO 每筆最多抓幾個商品頁", 1, 8, 3)
            delay = st.slider("請求間隔（秒）", 0.3, 3.0, 0.8, 0.1)
            max_attempts = st.slider("每池最多嘗試筆數", 5, 200, 50)
    
    # === 主區域 ===
    if up is None:
        # 未上傳時顯示使用說明
        st.info("👈 請先於左側上傳認證清單 Excel 檔案")
        # 顯示一個美觀的說明卡片
        with st.container():
            st.markdown("""### 📋 使用流程
            1. **上傳** — 左側上傳 NCC 認證清單 Excel
            2. **設定** — 選擇年份、設定各池抽樣數量
            3. **搜尋** — 系統自動到 Yahoo/MOMO/露天搜尋
            4. **結果** — 查看可購買商品、匯出報告
            """)
            st.markdown("""### 🎯 抽樣邏輯
            - **CCAN 池**：自家驗證機構 (cert[2:4]='AN') 的產品
            - **其他 RCB 池**：其餘驗證機構的產品
            - LP（低功率）和 TTE（電信終端）**各自獨立配額**
            - 隨機抽樣，湊不滿自動找下一筆
            """)
            st.markdown("""### 🔍 多層搜尋策略
            - **第 1 輪**：NCC ID 直搜（優先找有標示認證碼的商品）
            - **第 2 輪**：品牌 + 型號（補充搜尋）
            - **第 3 輪**：品牌 + 型號 + 產品類別（短型號補強）
            """)
        return
    
    # 解析 Excel
    try:
        items, report = parse_workbook(up.getvalue())
    except Exception as e:
        st.error(f"❌ 解析失敗：{e}")
        return
    
    cert_index = build_cert_index(items)
    
    # 解析報告
    with st.expander("📄 解析報告", expanded=False):
        for line in report:
            st.write(line)
    
    # 4 池統計儀表板
    pools = split_pools(items, year)
    st.markdown("### 📊 清單統計")
    cols = st.columns(4)
    pool_configs = [
        ("LPD_CCAN", "📡 LP-CCAN", "#6366f1"),
        ("LPD_OTHER", "📡 LP-其他", "#818cf8"),
        ("TTE_CCAN", "📱 TTE-CCAN", "#a855f7"),
        ("TTE_OTHER", "📱 TTE-其他", "#c084fc"),
    ]
    for i, (key, label, color) in enumerate(pool_configs):
        pool_count = len(pools.get(key, []))
        quota = {"LPD_CCAN": lpd_ccan, "LPD_OTHER": lpd_other, "TTE_CCAN": tte_ccan, "TTE_OTHER": tte_other}[key]
        cols[i].metric(label, f"{pool_count} 筆", delta=f"需抽 {quota} 筆")
    
    # 清單總數
    total_items = len(items)
    total_year = sum(len(v) for v in pools.values())
    st.caption(f"清單總計 {total_items} 筆，20{year}年共 {total_year} 筆")
    
    st.markdown("---")
    
    # 搜尋按鈕
    if st.button("🚀 開始自動搜尋核對", type="primary", width="stretch"):
        platforms = set()
        if use_yahoo: platforms.add("yahoo")
        if use_momo: platforms.add("momo")
        if use_ruten: platforms.add("ruten")
        
        if not platforms:
            st.warning("⚠️ 請至少勾選一個搜尋平台")
            return
        
        quotas = {
            "LPD_CCAN": lpd_ccan, "LPD_OTHER": lpd_other,
            "TTE_CCAN": tte_ccan, "TTE_OTHER": tte_other
        }
        
        total_need = sum(quotas.values())
        prog = st.progress(0.0)
        status_text = st.empty()
        
        # on_status 回呼函數來計算跨池進度
        progress_state = {"total_attempts": 0, "pool_confirmed": {"LPD_CCAN": 0, "LPD_OTHER": 0, "TTE_CCAN": 0, "TTE_OTHER": 0}}
        
        def on_status(pool_key, confirmed, need, attempts, item):
            progress_state["total_attempts"] += 1
            progress_state["pool_confirmed"][pool_key] = confirmed
            current_total_confirmed = sum(progress_state["pool_confirmed"].values())
            
            status_text.markdown(
                f"🔎 **[{pool_key}]** 搜尋中（已確認 {confirmed}/{need}，"
                f"已嘗試 {attempts} 筆）：`{item['brand']} {item['model']}`"
            )
            # 更新整體進度條
            if total_need > 0:
                prog.progress(min(current_total_confirmed / total_need, 1.0))
        
        with st.spinner("🔍 自動搜尋中，請稍候…"):
            rows = run_dual_pool(
                items, cert_index, year, quotas, platforms,
                max_detail=max_detail, delay=delay,
                max_attempts=max_attempts,
                price_min=price_min_val if price_min_val > 0 else None,
                price_max=price_max_val if price_max_val > 0 else None,
                on_status=on_status
            )
        
        prog.progress(1.0)
        status_text.empty()
        st.session_state["rows"] = rows
    
    # 顯示結果
    rows = st.session_state.get("rows")
    if rows:
        df = pd.DataFrame(rows)
        n_ok = sum(1 for r in rows if str(r.get("結果", "")).startswith("✅"))
        n_total = len(rows)
        
        st.markdown(f"### 📋 搜尋結果（確認上架 {n_ok} / 共查 {n_total} 筆）")
        
        # 結果統計卡片
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("✅ 確認上架", n_ok)
        sc2.metric("❌ 未找到", n_total - n_ok)
        sc3.metric("📊 命中率", f"{n_ok/max(n_total,1)*100:.0f}%")
        sc4.metric("🔍 總搜尋筆數", n_total)
        
        # 篩選 tabs
        tab_all, tab_ok, tab_fail = st.tabs(["全部", "✅ 已找到", "❌ 未找到"])
        
        col_config = {
            "賣場連結": st.column_config.LinkColumn("賣場連結", display_text="前往"),
            "Google購物": st.column_config.LinkColumn("Google", display_text="搜尋"),
            "露天": st.column_config.LinkColumn("露天", display_text="搜尋"),
            "酷澎": st.column_config.LinkColumn("酷澎", display_text="搜尋"),
            "蝦皮": st.column_config.LinkColumn("蝦皮", display_text="搜尋"),
        }
        
        with tab_all:
            st.dataframe(
                df, width="stretch", hide_index=True,
                column_config=col_config
            )
        
        with tab_ok:
            df_ok = df[df["結果"].astype(str).str.startswith("✅")]
            if not df_ok.empty:
                st.dataframe(df_ok, width="stretch", hide_index=True,
                    column_config=col_config
                )
            else:
                st.info("目前沒有確認上架的結果")
        
        with tab_fail:
            df_fail = df[~df["結果"].astype(str).str.startswith("✅")]
            if not df_fail.empty:
                st.dataframe(df_fail, width="stretch", hide_index=True,
                    column_config=col_config
                )
            else:
                st.info("全部都找到了！🎉")
        
        st.markdown("---")
        
        # 匯出按鈕
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            csv = "\ufeff" + df.to_csv(index=False)
            st.download_button(
                "📥 下載 CSV 報告", data=csv.encode("utf-8"),
                file_name=f"NCC自動核對結果_20{year}.csv", mime="text/csv",
                width="stretch"
            )
        with col_exp2:
            # Excel 匯出
            import io
            buf = io.BytesIO()
            df.to_excel(buf, index=False, engine="openpyxl")
            st.download_button(
                "📥 下載 Excel 報告", data=buf.getvalue(),
                file_name=f"NCC自動核對結果_20{year}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch"
            )

if __name__ == "__main__":
    main()
