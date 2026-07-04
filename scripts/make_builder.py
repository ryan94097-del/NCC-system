# -*- coding: utf-8 -*-
"""產生 builder.html：內嵌 app.js 與 SheetJS，於瀏覽器內以共用密碼 AES-GCM 加密，
輸出單一自足的 NCC核對工具.html。全程免 Python（使用者端）。"""
import base64, os

BASE = r"c:\Users\Ryan\Documents\Antigravity folder\NCC surveillance"
app_bytes = open(os.path.join(BASE, "src", "app.js"), "rb").read()
sheet_bytes = open(os.path.join(BASE, "src", "xlsx.full.min.js"), "rb").read()
app_b64 = base64.b64encode(app_bytes).decode()
sheet_b64 = base64.b64encode(sheet_bytes).decode()

# ─── 執行期外殼樣板（加密工具最終輸出的 HTML）───
# 佔位符：__SHEETJS_B64__ __SALT_B64__ __IV_B64__ __CT_B64__
WRAPPER = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NCC 案件賣場搜尋核對工具</title>
<style>
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{font-family:'Segoe UI','Microsoft JhengHei',sans-serif;background:#f1f5f9}
#gate{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#4f46e5,#9333ea)}
.card{background:#fff;border-radius:16px;padding:34px 40px;box-shadow:0 20px 60px rgba(0,0,0,.3);width:340px;text-align:center}
.card h1{font-size:20px;margin:0 0 4px}.card p{color:#6b7280;font-size:13px;margin:0 0 20px}
.card input{width:100%;padding:11px 12px;border:1px solid #d1d5db;border-radius:9px;font-size:15px;margin-bottom:12px}
.card button{width:100%;padding:11px;border:0;border-radius:9px;background:#4f46e5;color:#fff;font-size:15px;font-weight:700;cursor:pointer}
.card button:hover{background:#4338ca}
.err{color:#dc2626;font-size:13px;min-height:18px;margin-top:8px}
</style>
</head>
<body>
<div id="gate">
  <div class="card">
    <h1>🔒 NCC 賣場核對工具</h1>
    <p>請輸入共用密碼以開啟</p>
    <input id="pw" type="password" placeholder="密碼" autofocus>
    <button id="go">解鎖</button>
    <div class="err" id="err"></div>
  </div>
</div>
<div id="root"></div>
<script>
var SHEETJS_B64="__SHEETJS_B64__";
var PAYLOAD={salt:"__SALT_B64__",iv:"__IV_B64__",ct:"__CT_B64__"};
function b64ToBytes(b64){var bin=atob(b64);var u=new Uint8Array(bin.length);for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);return u;}
function bytesToText(u){return new TextDecoder().decode(u);}
// 載入 SheetJS（明文，非機密）
(function(){ try{ (0,eval)(bytesToText(b64ToBytes(SHEETJS_B64))); }catch(e){ console.error('SheetJS load fail',e);} })();
async function deriveKey(pw,salt){
  var enc=new TextEncoder();
  var km=await crypto.subtle.importKey('raw',enc.encode(pw),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2',salt:salt,iterations:200000,hash:'SHA-256'},km,{name:'AES-GCM',length:256},false,['decrypt']);
}
async function unlock(){
  var pw=document.getElementById('pw').value;
  var err=document.getElementById('err'); err.textContent='';
  try{
    var salt=b64ToBytes(PAYLOAD.salt),iv=b64ToBytes(PAYLOAD.iv),ct=b64ToBytes(PAYLOAD.ct);
    var key=await deriveKey(pw,salt);
    var pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:iv},key,ct);
    var appjs=bytesToText(new Uint8Array(pt));
    document.getElementById('gate').style.display='none';
    (0,eval)(appjs);
  }catch(e){ err.textContent='密碼錯誤，請重試。'; }
}
document.getElementById('go').onclick=unlock;
document.getElementById('pw').addEventListener('keydown',function(e){if(e.key==='Enter')unlock();});
</script>
</body>
</html>
"""
wrapper_b64 = base64.b64encode(WRAPPER.encode("utf-8")).decode()

# ─── builder.html（產生器 UI）───
BUILDER = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NCC 工具加密產生器 (builder)</title>
<style>
body{font-family:'Segoe UI','Microsoft JhengHei',sans-serif;background:#f8fafc;color:#1f2937;max-width:720px;margin:40px auto;padding:0 20px}
h1{font-size:22px}.box{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin:16px 0}
label{font-weight:600;display:block;margin:10px 0 4px}
input[type=text]{width:100%;padding:9px 12px;border:1px solid #d1d5db;border-radius:8px;font-size:15px}
button{padding:11px 20px;border:0;border-radius:9px;background:#4f46e5;color:#fff;font-weight:700;font-size:15px;cursor:pointer}
button:hover{background:#4338ca}.muted{color:#6b7280;font-size:13px}
.ok{color:#059669;font-weight:600}.small{font-size:12px}
details{margin-top:10px}summary{cursor:pointer;color:#4f46e5}
</style>
</head>
<body>
<h1>🔧 NCC 工具加密產生器</h1>
<p class="muted">輸入共用密碼 → 產生單一自足的 <b>NCC核對工具.html</b>（已內嵌工具與 SheetJS，離線可用、免安裝）。分享時把「檔案 + 密碼」給同事即可。</p>
<div class="box">
  <label>共用密碼</label>
  <input id="pw" type="text" value="ncc2026">
  <p class="muted small">預設 <code>ncc2026</code>，可自行修改；換密碼就重新產生一次即可。</p>
  <div style="margin-top:14px"><button id="build">產生加密工具 ⬇</button></div>
  <p id="status" class="muted"></p>
  <details>
    <summary>進階：更新工具內容（選用）</summary>
    <p class="muted small">若日後要更新工具邏輯，可上傳新的 app.js 覆蓋內建版本後再產生。</p>
    <label>app.js（選填）</label><input id="appFile" type="file" accept=".js">
  </details>
</div>
<script>
var APP_SRC_B64="%APP_B64%";
var SHEETJS_B64="%SHEET_B64%";
var WRAPPER_B64="%WRAPPER_B64%";
function b64ToText(b64){var bin=atob(b64);var u=new Uint8Array(bin.length);for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);return new TextDecoder().decode(u);}
function bytesToB64(u){var s='';for(var i=0;i<u.length;i++)s+=String.fromCharCode(u[i]);return btoa(s);}
var overrideApp=null;
document.getElementById('appFile').addEventListener('change',function(e){
  var f=e.target.files[0]; if(!f)return; var fr=new FileReader();
  fr.onload=function(){overrideApp=fr.result;document.getElementById('status').textContent='已載入自訂 app.js';};
  fr.readAsText(f);
});
async function buildEncrypted(password){
  var appText=overrideApp!=null?overrideApp:b64ToText(APP_SRC_B64);
  var wrapper=b64ToText(WRAPPER_B64);
  var enc=new TextEncoder();
  var salt=crypto.getRandomValues(new Uint8Array(16));
  var iv=crypto.getRandomValues(new Uint8Array(12));
  var km=await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveKey']);
  var key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:salt,iterations:200000,hash:'SHA-256'},km,{name:'AES-GCM',length:256},false,['encrypt']);
  var ct=await crypto.subtle.encrypt({name:'AES-GCM',iv:iv},key,enc.encode(appText));
  var html=wrapper
    .replace('__SHEETJS_B64__',SHEETJS_B64)
    .replace('__SALT_B64__',bytesToB64(salt))
    .replace('__IV_B64__',bytesToB64(iv))
    .replace('__CT_B64__',bytesToB64(new Uint8Array(ct)));
  return html;
}
window.__BUILD__=function(pw){return buildEncrypted(pw||document.getElementById('pw').value||'ncc2026');};
document.getElementById('build').onclick=async function(){
  var st=document.getElementById('status'); st.textContent='加密產生中…';
  try{
    var html=await window.__BUILD__();
    var blob=new Blob([html],{type:'text/html;charset=utf-8'});
    var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='NCC核對工具.html';
    document.body.appendChild(a);a.click();document.body.removeChild(a);
    st.innerHTML='<span class="ok">✅ 已產生 NCC核對工具.html（密碼：'+(document.getElementById('pw').value)+'）</span>';
  }catch(e){ st.textContent='產生失敗：'+e.message; }
};
</script>
</body>
</html>
"""
BUILDER = (BUILDER
           .replace("%APP_B64%", app_b64)
           .replace("%SHEET_B64%", sheet_b64)
           .replace("%WRAPPER_B64%", wrapper_b64))

out = os.path.join(BASE, "src", "builder.html")
open(out, "w", encoding="utf-8").write(BUILDER)
print("WROTE:", out, "size:", len(BUILDER))
