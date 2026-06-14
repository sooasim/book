// 콘텐츠 스크립트: 입력칸 자동 인식 + 저장 기본정보로 채우기 + (선택) 초안저장/다단계.
// 안전: 약관 체크/캡차/비밀번호/세금/계좌/최종 게시 버튼은 절대 건드리지 않는다.
(function () {
  "use strict";
  var KW = null, OVERRIDES = {};

  function res(name) { return fetch(chrome.runtime.getURL(name)).then(function (r) { return r.json(); }); }

  // 라벨 연결 강화: for=, 감싼 label, aria-labelledby, 직전 형제 텍스트
  function labelFor(el) {
    if (el.id) {
      var l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (l && l.textContent.trim()) return l.textContent;
    }
    var wrap = el.closest("label");
    if (wrap && wrap.textContent.trim()) return wrap.textContent;
    var lb = el.getAttribute("aria-labelledby");
    if (lb) {
      var parts = lb.split(/\s+/).map(function (id) {
        var n = document.getElementById(id); return n ? n.textContent : "";
      });
      if (parts.join(" ").trim()) return parts.join(" ");
    }
    // 직전 형제/부모의 라벨류 텍스트
    var prev = el.previousElementSibling;
    if (prev && /label|span|div|dt|th/i.test(prev.tagName) && prev.textContent.trim().length < 40)
      return prev.textContent;
    return "";
  }

  function collect() {
    var out = [];
    document.querySelectorAll("input, textarea, select, [contenteditable='true']").forEach(function (el) {
      var tag = el.tagName.toLowerCase();
      var type = (el.getAttribute("type") || (tag === "textarea" ? "textarea" : "")).toLowerCase();
      if (tag === "input" && ["hidden", "submit", "button", "checkbox", "radio", "password"].indexOf(type) !== -1) return;
      if (el.disabled || el.readOnly) return;
      if (el.offsetParent === null && tag !== "select") return; // 숨김 제외
      out.push({ ref: el, attrs: {
        tag: tag, type: type, name: el.getAttribute("name"), id: el.id,
        placeholder: el.getAttribute("placeholder"), aria_label: el.getAttribute("aria-label"),
        label: labelFor(el), data_test: el.getAttribute("data-testid") } });
    });
    return out;
  }

  function queryOverride(spec) {
    try {
      if (spec.by === "id") return document.getElementById(spec.selector);
      if (spec.by === "name") return document.querySelector('[name="' + CSS.escape(spec.selector) + '"]');
      return document.querySelector(spec.selector); // css
    } catch (e) { return null; }
  }

  function setValue(el, value) {
    var tag = el.tagName.toLowerCase();
    if (el.isContentEditable) { el.textContent = value; }
    else if (tag === "select") {
      var opt = Array.prototype.find.call(el.options, function (o) {
        return o.textContent.trim() === value || o.value === value; });
      if (opt) el.value = opt.value; else return false;
    } else { el.value = value; }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function highlight(el, color) { try { el.style.outline = "2px solid " + color; } catch (e) {} }

  function fillOnce(profile) {
    var filled = [], manual = [], skipped = [];
    var host = location.hostname;
    var ov = window.OCESFieldMatch.resolveOverrides(host, OVERRIDES);
    var done = {};
    // 1) 사이트별 명시 보정 먼저
    Object.keys(ov).forEach(function (key) {
      var el = queryOverride(ov[key]); if (!el) return;
      var val = window.OCESFieldMatch.profileValue(profile, key);
      if (val == null || val === "") return;
      if (setValue(el, val)) { filled.push(key); done[key] = true; highlight(el, "#d1fae5"); }
    });
    // 2) 휴리스틱으로 나머지
    var plan = window.OCESFieldMatch.buildFillPlan(profile, collect(), KW);
    plan.forEach(function (step) {
      if (done[step.field_key]) return;
      if (step.kind === "fill") {
        if (setValue(step.ref, step.value)) { filled.push(step.field_key); highlight(step.ref, "#d1fae5"); }
        else skipped.push(step.field_key);
      } else if (step.kind === "file_manual") { manual.push(step.field_key); highlight(step.ref, "#fef3c7"); }
    });
    return { filled: filled, manual: manual, skipped: skipped };
  }

  // 클릭 가능한 버튼/링크 수집 → 안전 버튼만 반환(최종 버튼은 절대 제외)
  function findButtons() {
    var nodes = document.querySelectorAll(
      "button, input[type='submit'], input[type='button'], [role='button'], a.btn, a.button");
    var safe = [], finals = [];
    nodes.forEach(function (el) {
      if (el.disabled || el.offsetParent === null) return;
      var text = (el.value || el.textContent || el.getAttribute("aria-label") || "").trim();
      var cls = window.OCESFieldMatch.classifyButton(text, KW);
      if (cls === "final") finals.push({ el: el, text: text });
      else if (cls === "safe") safe.push({ el: el, text: text });
    });
    return { safe: safe, finals: finals };
  }

  function getProfile() {
    return new Promise(function (resolve) {
      chrome.storage.local.get("oces_profile", function (d) { resolve(d.oces_profile || {}); });
    });
  }

  // 단순 채움
  function runFill() {
    return getProfile().then(function (p) { var r = fillOnce(p); showPanel(r); return r; });
  }

  // 채움 + 안전 버튼(임시저장/다음) 1회 클릭 (최종 게시 직전까지). 최종 버튼은 절대 클릭 안 함.
  function runSaveDraft() {
    return getProfile().then(function (p) {
      var r = fillOnce(p);
      var btns = findButtons();
      var clicked = null;
      if (btns.safe.length) { btns.safe[0].el.click(); clicked = btns.safe[0].text; }
      r.clicked = clicked; r.finals_present = btns.finals.map(function (b) { return b.text; });
      showPanel(r, clicked ? ("'" + clicked + "' 클릭") : "안전 버튼 없음");
      return r;
    });
  }

  // 다단계 폼: 채움 → 안전 '다음/저장' 클릭 → DOM 변화 대기 → 반복. 최종 게시 직전에서 정지.
  function runMultiStep(maxSteps) {
    maxSteps = maxSteps || 6;
    return getProfile().then(function (p) {
      var log = [];
      function step(i) {
        if (i >= maxSteps) return Promise.resolve();
        var r = fillOnce(p);
        log.push({ step: i + 1, filled: r.filled.length });
        var btns = findButtons();
        // 안전 '다음/저장' 후보(이전/미리보기 제외) 우선
        var nav = btns.safe.find(function (b) {
          var t = b.text.toLowerCase();
          return /다음|계속|저장|next|continue|save/.test(t) && !/이전|미리보기|back|preview/.test(t);
        });
        if (!nav) return Promise.resolve();          // 더 진행할 안전 단계 없음 → 정지
        nav.el.click();
        return new Promise(function (resolve) { setTimeout(resolve, 1200); }).then(function () { return step(i + 1); });
      }
      return step(0).then(function () {
        var btns = findButtons();
        showPanel({ filled: ["다단계 " + log.length + "단계"], manual: [], skipped: [] },
          "최종 게시 버튼(" + btns.finals.map(function (b) { return b.text; }).join(", ") + ")은 직접 클릭하세요");
      });
    });
  }

  function ui() {
    if (document.getElementById("oces-fab")) return;
    var fab = document.createElement("button");
    fab.id = "oces-fab"; fab.textContent = "📚 자동 채우기";
    fab.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:2147483647;background:#111;color:#fff;" +
      "border:none;border-radius:24px;padding:10px 16px;font-size:14px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.3)";
    fab.onclick = function () { runFill(); };
    document.documentElement.appendChild(fab);
  }

  function showPanel(r, extra) {
    var old = document.getElementById("oces-panel"); if (old) old.remove();
    var box = document.createElement("div"); box.id = "oces-panel";
    box.style.cssText = "position:fixed;right:16px;bottom:64px;z-index:2147483647;background:#fff;color:#111;" +
      "border:1px solid #ddd;border-radius:10px;padding:12px 14px;font-size:13px;max-width:340px;" +
      "box-shadow:0 4px 16px rgba(0,0,0,.2);line-height:1.6";
    box.innerHTML = "<b>자동 채움 결과</b><br>✅ 채움: " + ((r.filled || []).join(", ") || "없음") +
      "<br>📎 직접 첨부: " + ((r.manual || []).join(", ") || "없음") +
      (extra ? "<br>▶ " + extra : "") +
      "<br><span style='color:#b45309'>※ 약관·본인인증·세금·최종 게시는 직접 확인/클릭하세요.</span>";
    document.documentElement.appendChild(box);
    setTimeout(function () { box.remove(); }, 9000);
  }

  chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
    if (!msg || !msg.type) return;
    var p = msg.type === "OCES_FILL" ? runFill()
          : msg.type === "OCES_SAVE_DRAFT" ? runSaveDraft()
          : msg.type === "OCES_MULTISTEP" ? runMultiStep(msg.maxSteps)
          : null;
    if (p) { p.then(function (r) { sendResponse(r || { ok: true }); }); return true; }
  });

  Promise.all([res("field_keywords.json"), res("site_overrides.json")]).then(function (a) {
    KW = a[0]; OVERRIDES = a[1] || {}; ui();
  });
})();
