/* NCC 案件賣場搜尋核對工具 — 應用邏輯
 * 純前端；渲染到 #root；使用全域 XLSX (SheetJS)。
 * 這整支檔案就是「加密酬載」，builder 會把它加密進單一 HTML。
 */
(function () {
  "use strict";

  // ────────────────────────────── 常數 ──────────────────────────────
  var LS_KEY = "ncc_worksheet_v1";
  var STATUS_OPTIONS = ["未查", "已上架", "未上架", "存疑"];
  var MARKETS = [
    { id: "momo",    name: "MOMO",   url: function (kw) { return "https://www.momoshop.com.tw/search/searchShop.jsp?keyword=" + kw + "&searchType=1"; } },
    { id: "yahoo",   name: "Yahoo",  url: function (kw) { return "https://tw.buy.yahoo.com/search/product?p=" + kw; } },
    { id: "google",  name: "Google", url: function (kw) { return "https://www.google.com/search?tbm=shop&q=" + kw; } },
    { id: "ruten",   name: "露天",   url: function (kw) { return "https://find.ruten.com.tw/s/?q=" + kw; } },
    { id: "coupang", name: "酷澎",   url: function (kw) { return "https://www.tw.coupang.com/search?q=" + kw; } },
    { id: "shopee",  name: "蝦皮",   url: function (kw) { return "https://shopee.tw/search?keyword=" + kw; } }
  ];

  // ────────────────────────────── 狀態 ──────────────────────────────
  var state = {
    items: [],            // 全部解析後的案件
    filtered: [],         // 套用年份/模式後
    ws: loadWorksheet(),  // 核對進度 { itemId: {status,seller,price,note,shots:[dataURL]} }
    year: "26",
    sampleMode: false,
    sampleN: 5,
    markets: MARKETS.reduce(function (a, m) { a[m.id] = true; return a; }, {}),
    activeShotTarget: null // 目前接受貼上截圖的 itemId
  };

  // ────────────────────────────── 工具函式 ──────────────────────────────
  function norm(s) { return String(s == null ? "" : s).replace(/\s+/g, "").toLowerCase(); }
  function cleanCert(s) {
    // 去掉換行後的附註(如「\n(系列1)」)與前後空白
    return String(s == null ? "" : s).split(/[\r\n]/)[0].trim();
  }
  function yearOf(cert) {
    var c = cleanCert(cert).toUpperCase();
    return (c.length >= 6 && c.indexOf("CC") === 0) ? c.substring(4, 6) : "";
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function isGenericModel(m) {
    m = String(m || "").trim();
    return m.length < 4 || /^[0-9]+$/.test(m);
  }
  function chineseOf(s) {
    var m = String(s || "").match(/[一-鿿][一-鿿0-9A-Za-z]*/g);
    return m ? m.join("") : "";
  }
  function defaultKeyword(brand, model, product) {
    var base = (String(brand || "").trim() + " " + String(model || "").trim()).trim();
    if (isGenericModel(model)) {
      var cat = chineseOf(product);
      if (cat) base = (base + " " + cat).trim();
    }
    return base;
  }
  function itemId(it) { return it.cat + "|" + it.cert + "|" + it.model; }

  // ────────────────────────────── 進度儲存 ──────────────────────────────
  function loadWorksheet() {
    try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; }
    catch (e) { return {}; }
  }
  function saveWorksheet() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(state.ws)); } catch (e) {}
  }
  function wsOf(id) {
    if (!state.ws[id]) state.ws[id] = { status: "未查", seller: "", price: "", note: "", kw: "", shots: [] };
    return state.ws[id];
  }

  // ────────────────────────────── Excel/CSV 解析 ──────────────────────────────
  function parseWorkbook(data, isCsv) {
    var wb = isCsv
      ? XLSX.read(data, { type: "string", raw: true })
      : XLSX.read(data, { type: "array" });
    var items = [];
    var report = [];

    wb.SheetNames.forEach(function (sn) {
      var up = sn.toUpperCase();
      var cat = up.indexOf("LPD") >= 0 ? "LPD" : (up.indexOf("TTE") >= 0 ? "TTE" : null);
      if (isCsv) cat = "CSV";
      if (!cat) return;

      var aoa = XLSX.utils.sheet_to_json(wb.Sheets[sn], { header: 1, defval: "", raw: false });
      if (!aoa.length) return;

      // 找表頭列：同時含「證書編號」與「型號」
      var hIdx = -1;
      for (var i = 0; i < Math.min(aoa.length, 15); i++) {
        var vals = aoa[i].map(norm);
        if (vals.indexOf(norm("證書編號")) >= 0 && vals.indexOf(norm("型號")) >= 0) { hIdx = i; break; }
      }
      if (hIdx < 0) { report.push("⚠️ 分頁「" + sn + "」找不到表頭(證書編號+型號)，略過"); return; }

      var header = aoa[hIdx].map(function (h) { return norm(h); });
      function col(name) { return header.indexOf(norm(name)); }
      var cCert = col("證書編號"), cModel = col("型號"), cBrand = col("廠牌"), cProd = col("委託產品");
      if (cCert < 0 || cModel < 0) { report.push("⚠️ 分頁「" + sn + "」缺欄位，略過"); return; }

      var kept = 0, raw = 0;
      for (var r = hIdx + 1; r < aoa.length; r++) {
        var row = aoa[r];
        var cert = cleanCert(row[cCert]);
        var model = String(row[cModel] == null ? "" : row[cModel]).trim();
        raw++;
        if (!cert || cert.toUpperCase().indexOf("CC") !== 0) continue; // 濾年份分隔列/請款列/雜列
        if (!model) continue;
        var brand = cBrand >= 0 ? String(row[cBrand] || "").trim() : "";
        var product = cProd >= 0 ? String(row[cProd] || "").trim() : "";
        items.push({
          cat: cat, cert: cert, brand: brand, model: model, product: product,
          year: yearOf(cert)
        });
        kept++;
      }
      report.push("✅ 分頁「" + sn + "」(" + cat + ")：讀入 " + kept + " 筆有效案件");
    });

    // 去重(同 cat+cert+model)
    var seen = {}, dedup = [];
    items.forEach(function (it) {
      var k = itemId(it);
      if (!seen[k]) { seen[k] = 1; dedup.push(it); }
    });
    return { items: dedup, report: report };
  }

  // ────────────────────────────── 篩選 ──────────────────────────────
  function applyFilter() {
    var yr = state.year;
    var byYear = state.items.filter(function (it) { return it.year === yr; });
    if (!state.sampleMode) { state.filtered = byYear; return; }
    // 抽樣：每分類前 N 筆
    var counts = {}, out = [];
    byYear.forEach(function (it) {
      counts[it.cat] = counts[it.cat] || 0;
      if (counts[it.cat] < state.sampleN) { out.push(it); counts[it.cat]++; }
    });
    state.filtered = out;
  }

  // ────────────────────────────── 匯出 ──────────────────────────────
  function collectRows() {
    return state.filtered.map(function (it) {
      var w = wsOf(itemId(it));
      var kw = (w.kw && w.kw.trim()) || defaultKeyword(it.brand, it.model, it.product);
      return { it: it, w: w, kw: kw };
    });
  }
  function download(filename, blob) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a); a.click();
    setTimeout(function () { document.body.removeChild(a); URL.revokeObjectURL(a.href); }, 100);
  }
  function exportCSV() {
    var rows = collectRows();
    var head = ["分類", "證書編號", "廠牌", "型號", "委託產品", "核對狀態", "賣家", "價格", "備註", "搜尋關鍵字", "截圖數"];
    var lines = [head.join(",")];
    rows.forEach(function (x) {
      var line = [x.it.cat, x.it.cert, x.it.brand, x.it.model, x.it.product,
        x.w.status, x.w.seller, x.w.price, x.w.note, x.kw, (x.w.shots || []).length];
      lines.push(line.map(function (v) {
        v = String(v == null ? "" : v).replace(/"/g, '""');
        return /[",\n]/.test(v) ? '"' + v + '"' : v;
      }).join(","));
    });
    var bom = "﻿";
    download("NCC核對結果_20" + state.year + ".csv",
      new Blob([bom + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
  }
  function exportXLSX() {
    var rows = collectRows();
    var aoa = [["分類", "證書編號", "廠牌", "型號", "委託產品", "核對狀態", "賣家", "價格", "備註", "搜尋關鍵字", "截圖數"]];
    rows.forEach(function (x) {
      aoa.push([x.it.cat, x.it.cert, x.it.brand, x.it.model, x.it.product,
        x.w.status, x.w.seller, x.w.price, x.w.note, x.kw, (x.w.shots || []).length]);
    });
    var ws = XLSX.utils.aoa_to_sheet(aoa);
    var wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "核對結果");
    XLSX.writeFile(wb, "NCC核對結果_20" + state.year + ".xlsx");
  }
  function exportHTMLReport() {
    var rows = collectRows();
    var body = rows.map(function (x) {
      var links = MARKETS.map(function (m) {
        return '<a href="' + esc(m.url(encodeURIComponent(x.kw))) + '" target="_blank">' + m.name + "</a>";
      }).join(" ");
      var shots = (x.w.shots || []).map(function (s) {
        return '<img src="' + s + '" style="max-width:180px;max-height:140px;margin:2px;border:1px solid #ccc;border-radius:4px">';
      }).join("");
      return "<tr>" +
        "<td>" + esc(x.it.cat) + "</td>" +
        "<td>" + esc(x.it.cert) + "</td>" +
        "<td>" + esc(x.it.brand) + "</td>" +
        "<td>" + esc(x.it.model) + "</td>" +
        "<td>" + esc(x.it.product) + "</td>" +
        "<td><b>" + esc(x.w.status) + "</b></td>" +
        "<td>" + esc(x.w.seller) + "</td>" +
        "<td>" + esc(x.w.price) + "</td>" +
        "<td>" + esc(x.w.note) + "</td>" +
        "<td>" + links + "</td>" +
        "<td>" + shots + "</td>" +
        "</tr>";
    }).join("");
    var html = "<!DOCTYPE html><html lang=zh-Hant><head><meta charset=utf-8>" +
      "<title>NCC 核對報告 20" + state.year + "</title><style>" +
      "body{font-family:'Segoe UI','Microsoft JhengHei',sans-serif;margin:24px;color:#222}" +
      "h1{font-size:20px}table{border-collapse:collapse;width:100%;font-size:13px}" +
      "th,td{border:1px solid #ddd;padding:6px 8px;vertical-align:top}th{background:#f3f4f6}" +
      "a{display:inline-block;margin:1px 4px;color:#2563eb}</style></head><body>" +
      "<h1>NCC 案件賣場核對報告 — 20" + state.year + " 年（共 " + rows.length + " 筆）</h1>" +
      "<p>產生時間：" + new Date().toLocaleString() + "</p>" +
      "<table><thead><tr><th>分類</th><th>證書編號</th><th>廠牌</th><th>型號</th><th>委託產品</th>" +
      "<th>狀態</th><th>賣家</th><th>價格</th><th>備註</th><th>賣場搜尋</th><th>截圖</th></tr></thead>" +
      "<tbody>" + body + "</tbody></table></body></html>";
    download("NCC核對報告_20" + state.year + ".html", new Blob([html], { type: "text/html;charset=utf-8" }));
  }
  function exportProgress() {
    download("NCC核對進度_" + new Date().toISOString().slice(0, 10) + ".json",
      new Blob([JSON.stringify(state.ws, null, 2)], { type: "application/json" }));
  }
  function importProgress(file) {
    var fr = new FileReader();
    fr.onload = function () {
      try {
        var obj = JSON.parse(fr.result);
        Object.keys(obj).forEach(function (k) { state.ws[k] = obj[k]; });
        saveWorksheet(); render();
        toast("已匯入進度");
      } catch (e) { toast("進度檔格式錯誤", true); }
    };
    fr.readAsText(file);
  }

  // ────────────────────────────── 截圖處理 ──────────────────────────────
  function addShot(id, dataURL) {
    var w = wsOf(id);
    w.shots = w.shots || [];
    w.shots.push(dataURL);
    saveWorksheet(); render();
  }
  function fileToDataURL(file, cb) {
    var fr = new FileReader();
    fr.onload = function () { cb(fr.result); };
    fr.readAsDataURL(file);
  }
  document.addEventListener("paste", function (e) {
    if (!state.activeShotTarget) return;
    var items = (e.clipboardData || {}).items || [];
    for (var i = 0; i < items.length; i++) {
      if (items[i].type && items[i].type.indexOf("image") === 0) {
        var f = items[i].getAsFile();
        fileToDataURL(f, function (d) { addShot(state.activeShotTarget, d); });
        e.preventDefault();
        break;
      }
    }
  });

  // ────────────────────────────── UI 渲染 ──────────────────────────────
  function injectStyle() {
    if (document.getElementById("ncc-style")) return;
    var s = document.createElement("style");
    s.id = "ncc-style";
    s.textContent =
      "*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI','Microsoft JhengHei',sans-serif;color:#1f2937;background:#f8fafc}" +
      ".wrap{max-width:1400px;margin:0 auto;padding:16px}" +
      ".title{font-size:22px;font-weight:800;background:linear-gradient(135deg,#4f46e5,#9333ea);-webkit-background-clip:text;background-clip:text;color:transparent}" +
      ".sub{color:#6b7280;font-size:13px;margin:4px 0 14px}" +
      ".panel{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.05)}" +
      ".ctrls{display:flex;flex-wrap:wrap;gap:14px;align-items:center}" +
      ".ctrls label{font-size:13px;font-weight:600;margin-right:4px}" +
      "select,input[type=text],input[type=number]{border:1px solid #d1d5db;border-radius:6px;padding:5px 8px;font-size:13px}" +
      ".mk{display:inline-flex;align-items:center;gap:3px;font-size:12px;background:#eef2ff;padding:2px 8px;border-radius:999px}" +
      ".btn{border:0;border-radius:8px;padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer;color:#fff;background:#4f46e5}" +
      ".btn.g{background:#059669}.btn.k{background:#6b7280}.btn.sm{padding:5px 10px;font-size:12px}" +
      ".stat{display:inline-block;background:#f1f5f9;border-radius:8px;padding:8px 14px;margin-right:10px;font-size:13px}" +
      ".stat b{font-size:18px;color:#4f46e5;display:block}" +
      "table.ws{border-collapse:collapse;width:100%;font-size:12.5px;background:#fff}" +
      "table.ws th,table.ws td{border:1px solid #e5e7eb;padding:5px 6px;vertical-align:top}" +
      "table.ws th{background:#f3f4f6;position:sticky;top:0;z-index:1}" +
      ".lpd{color:#4338ca;font-weight:700}.tte{color:#be185d;font-weight:700}" +
      ".mlink{display:inline-block;margin:1px;padding:2px 7px;border-radius:6px;background:#eff6ff;color:#1d4ed8;text-decoration:none;font-size:11.5px}" +
      ".mlink:hover{background:#dbeafe}" +
      ".shots img{max-width:70px;max-height:52px;margin:1px;border:1px solid #ccc;border-radius:4px;cursor:pointer}" +
      ".drop{border:1px dashed #cbd5e1;border-radius:6px;padding:4px;font-size:11px;color:#94a3b8;text-align:center;cursor:pointer}" +
      ".drop.active{border-color:#4f46e5;color:#4f46e5;background:#eef2ff}" +
      ".logs{font-family:monospace;font-size:12px;white-space:pre-wrap;background:#0f172a;color:#a7f3d0;border-radius:8px;padding:10px;max-height:160px;overflow:auto}" +
      "#toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#111827;color:#fff;padding:10px 18px;border-radius:8px;font-size:13px;opacity:0;transition:.3s;pointer-events:none;z-index:99}" +
      "#toast.show{opacity:1}#toast.err{background:#b91c1c}";
    document.head.appendChild(s);
  }

  function toast(msg, isErr) {
    var t = document.getElementById("toast");
    if (!t) { t = document.createElement("div"); t.id = "toast"; document.body.appendChild(t); }
    t.textContent = msg; t.className = "show" + (isErr ? " err" : "");
    clearTimeout(t._t); t._t = setTimeout(function () { t.className = ""; }, 2200);
  }

  function render() {
    applyFilter();
    var root = document.getElementById("root");
    var yrOpts = [];
    for (var y = 14; y <= 30; y++) { var yy = ("0" + y).slice(-2); yrOpts.push(yy); }

    var html = '<div class="wrap">';
    html += '<div class="title">🔍 NCC 案件賣場搜尋核對工具</div>';
    html += '<div class="sub">上傳認證清單 → 篩選 → 一鍵開六大賣場搜尋 → 人工核對記錄(狀態/賣家/價格/截圖) → 匯出報告。已排除 PChome。</div>';

    // 上傳
    html += '<div class="panel"><label>📁 上傳認證清單(Excel/CSV)：</label> <input type="file" id="file" accept=".xlsx,.xls,.csv"> ' +
      '<button class="btn k sm" id="loadSample" title="載入內建去識別化樣本">載入測試樣本</button></div>';

    if (state.items.length) {
      // 控制列
      html += '<div class="panel"><div class="ctrls">';
      html += '<span><label>🗓️ 年份</label><select id="year">' + yrOpts.map(function (o) {
        return '<option value="' + o + '"' + (o === state.year ? " selected" : "") + '>20' + o + "</option>";
      }).join("") + "</select></span>";
      html += '<span><label><input type="checkbox" id="sampleMode"' + (state.sampleMode ? " checked" : "") + '> 抽樣模式(每分類前</label>' +
        '<input type="number" id="sampleN" value="' + state.sampleN + '" min="1" max="999" style="width:64px"> 筆)</span>';
      html += '<span>' + MARKETS.map(function (m) {
        return '<span class="mk"><input type="checkbox" data-mk="' + m.id + '"' + (state.markets[m.id] ? " checked" : "") + '> ' + m.name + "</span>";
      }).join("") + "</span>";
      html += "</div></div>";

      // 統計
      var byCat = {};
      state.filtered.forEach(function (it) { byCat[it.cat] = (byCat[it.cat] || 0) + 1; });
      var done = 0;
      state.filtered.forEach(function (it) { var w = state.ws[itemId(it)]; if (w && w.status && w.status !== "未查") done++; });
      html += '<div class="panel">';
      html += '<span class="stat"><b>' + state.items.length + "</b>總案件</span>";
      html += '<span class="stat"><b>' + state.filtered.length + "</b>20" + state.year + " 年待查</span>";
      Object.keys(byCat).forEach(function (c) { html += '<span class="stat"><b>' + byCat[c] + "</b>" + c + "</span>"; });
      html += '<span class="stat"><b>' + done + "</b>已核對</span>";
      html += ' &nbsp; <button class="btn g sm" id="expHtml">📄 匯出HTML報告</button> ' +
        '<button class="btn g sm" id="expXlsx">📊 匯出Excel</button> ' +
        '<button class="btn g sm" id="expCsv">📑 匯出CSV</button> ' +
        '<button class="btn k sm" id="expProg">💾 匯出進度</button> ' +
        '<button class="btn k sm" id="impProg">📂 匯入進度</button>' +
        '<input type="file" id="progFile" accept=".json" style="display:none">';
      html += "</div>";

      // 工作表
      html += '<div class="panel" style="overflow:auto"><table class="ws"><thead><tr>' +
        "<th>分類</th><th>證書編號</th><th>廠牌 / 型號</th><th>委託產品</th><th>搜尋關鍵字</th>" +
        "<th>賣場一鍵搜尋</th><th>狀態</th><th>賣家</th><th>價格</th><th>備註</th><th>截圖(貼上/拖放)</th></tr></thead><tbody>";

      if (!state.filtered.length) {
        html += '<tr><td colspan="11" style="text-align:center;color:#94a3b8">此年份沒有案件，請調整年份。</td></tr>';
      }
      state.filtered.forEach(function (it) {
        var id = itemId(it), w = wsOf(id);
        var kw = (w.kw && w.kw.trim()) || defaultKeyword(it.brand, it.model, it.product);
        var enc = encodeURIComponent(kw);
        var links = MARKETS.filter(function (m) { return state.markets[m.id]; }).map(function (m) {
          return '<a class="mlink" href="' + esc(m.url(enc)) + '" target="_blank" rel="noopener">' + m.name + "▸</a>";
        }).join("");
        var shots = (w.shots || []).map(function (s, i) {
          return '<img src="' + s + '" data-del="' + id + "|" + i + '" title="點擊刪除">';
        }).join("");
        html += "<tr>" +
          '<td class="' + it.cat.toLowerCase() + '">' + esc(it.cat) + "</td>" +
          "<td>" + esc(it.cert) + "</td>" +
          "<td><b>" + esc(it.brand) + "</b><br>" + esc(it.model) + "</td>" +
          "<td>" + esc(it.product) + "</td>" +
          '<td><input type="text" data-kw="' + id + '" value="' + esc(kw) + '" style="width:150px"></td>' +
          '<td style="min-width:150px">' + links + "</td>" +
          '<td><select data-f="status" data-id="' + id + '">' + STATUS_OPTIONS.map(function (o) {
            return '<option' + (w.status === o ? " selected" : "") + ">" + o + "</option>";
          }).join("") + "</select></td>" +
          '<td><input type="text" data-f="seller" data-id="' + id + '" value="' + esc(w.seller) + '" style="width:90px"></td>' +
          '<td><input type="text" data-f="price" data-id="' + id + '" value="' + esc(w.price) + '" style="width:70px"></td>' +
          '<td><input type="text" data-f="note" data-id="' + id + '" value="' + esc(w.note) + '" style="width:110px"></td>' +
          '<td class="shots"><div class="drop" data-drop="' + id + '">貼上/拖放圖片</div>' + shots + "</td>" +
          "</tr>";
      });
      html += "</tbody></table></div>";
    }

    html += "</div>"; // wrap
    root.innerHTML = html;
    bind();
  }

  // ────────────────────────────── 事件綁定 ──────────────────────────────
  function bind() {
    var file = document.getElementById("file");
    if (file) file.onchange = function (e) { handleFile(e.target.files[0]); };
    var ls = document.getElementById("loadSample");
    if (ls) ls.onclick = loadSample;

    var yr = document.getElementById("year");
    if (yr) yr.onchange = function () { state.year = yr.value; render(); };
    var sm = document.getElementById("sampleMode");
    if (sm) sm.onchange = function () { state.sampleMode = sm.checked; render(); };
    var sn = document.getElementById("sampleN");
    if (sn) sn.onchange = function () { state.sampleN = Math.max(1, parseInt(sn.value, 10) || 1); render(); };
    Array.prototype.forEach.call(document.querySelectorAll("[data-mk]"), function (cb) {
      cb.onchange = function () { state.markets[cb.getAttribute("data-mk")] = cb.checked; render(); };
    });

    // 匯出/匯入
    var b;
    if ((b = document.getElementById("expHtml"))) b.onclick = exportHTMLReport;
    if ((b = document.getElementById("expXlsx"))) b.onclick = exportXLSX;
    if ((b = document.getElementById("expCsv"))) b.onclick = exportCSV;
    if ((b = document.getElementById("expProg"))) b.onclick = exportProgress;
    if ((b = document.getElementById("impProg"))) b.onclick = function () { document.getElementById("progFile").click(); };
    var pf = document.getElementById("progFile");
    if (pf) pf.onchange = function (e) { if (e.target.files[0]) importProgress(e.target.files[0]); };

    // 欄位編輯
    Array.prototype.forEach.call(document.querySelectorAll("[data-f]"), function (el) {
      el.oninput = el.onchange = function () {
        var w = wsOf(el.getAttribute("data-id"));
        w[el.getAttribute("data-f")] = el.value;
        saveWorksheet();
      };
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-kw]"), function (el) {
      el.oninput = function () { wsOf(el.getAttribute("data-kw")).kw = el.value; saveWorksheet(); };
      el.onchange = function () { render(); };
    });

    // 截圖：拖放 + 設定貼上目標
    Array.prototype.forEach.call(document.querySelectorAll("[data-drop]"), function (dz) {
      var id = dz.getAttribute("data-drop");
      dz.onclick = function () {
        state.activeShotTarget = id;
        Array.prototype.forEach.call(document.querySelectorAll("[data-drop]"), function (x) { x.className = "drop"; });
        dz.className = "drop active"; dz.textContent = "▶ 現在按 Ctrl+V 貼上";
      };
      dz.ondragover = function (e) { e.preventDefault(); dz.className = "drop active"; };
      dz.ondragleave = function () { dz.className = "drop"; };
      dz.ondrop = function (e) {
        e.preventDefault(); dz.className = "drop";
        var f = e.dataTransfer.files[0];
        if (f && f.type.indexOf("image") === 0) fileToDataURL(f, function (d) { addShot(id, d); });
      };
    });
    // 刪除截圖（itemId 內含「|」，以最後一個「|」切出索引）
    Array.prototype.forEach.call(document.querySelectorAll(".shots img"), function (img) {
      img.onclick = function () {
        var raw = img.getAttribute("data-del");
        var idx = parseInt(raw.slice(raw.lastIndexOf("|") + 1), 10);
        var id = raw.slice(0, raw.lastIndexOf("|"));
        var w = wsOf(id);
        if (w.shots && w.shots.length > idx) { w.shots.splice(idx, 1); saveWorksheet(); render(); }
      };
    });
  }

  // ────────────────────────────── 檔案讀取 ──────────────────────────────
  function handleFile(file) {
    if (!file) return;
    var isCsv = /\.csv$/i.test(file.name);
    var fr = new FileReader();
    fr.onload = function () {
      try {
        var res = isCsv ? parseWorkbook(fr.result, true)
                        : parseWorkbook(new Uint8Array(fr.result), false);
        if (!res.items.length) { toast("未讀到有效案件，請確認檔案", true); }
        state.items = res.items;
        render();
        toast("已讀入 " + res.items.length + " 筆案件");
      } catch (e) { toast("解析失敗：" + e.message, true); }
    };
    if (isCsv) fr.readAsText(file); else fr.readAsArrayBuffer(file);
  }

  // 內建測試樣本(去識別化)：直接以資料建立，供沒有檔案時試跑
  function loadSample() {
    state.items = [
      { cat: "LPD", cert: "CCAN26LP0010T1", brand: "ACME", model: "AX-100", product: "藍牙耳機", year: "26" },
      { cat: "LPD", cert: "CCAN26LP0020T4", brand: "FooTech", model: "FT-2200", product: "無線滑鼠", year: "26" },
      { cat: "LPD", cert: "CCAN26LP0030T7", brand: "BrandX", model: "溫濕度感應器 TH-9", product: "智慧溫濕度感應器", year: "26" },
      { cat: "LPD", cert: "CCAN26LP0040T0", brand: "GenCorp", model: "X8", product: "車用多媒體盒", year: "26" },
      { cat: "TTE", cert: "CCAN264G0010T8", brand: "PetGlobal", model: "PG-24A01", product: "寵物穿戴式定位通訊器", year: "26" },
      { cat: "TTE", cert: "CCAN264G0020T1", brand: "AutoLink", model: "ALX-8", product: "車用多媒體盒", year: "26" }
    ];
    render();
    toast("已載入內建測試樣本(6 筆)");
  }

  // ────────────────────────────── 啟動 ──────────────────────────────
  injectStyle();
  render();
  window.__NCC_READY__ = true;
  // 內部除錯/測試把手（不影響一般使用）
  window.__NCC__ = {
    parse: parseWorkbook, handleFile: handleFile, state: state,
    defaultKeyword: defaultKeyword, yearOf: yearOf, cleanCert: cleanCert,
    applyFilter: applyFilter, render: render, wsOf: wsOf, saveWorksheet: saveWorksheet
  };
})();
