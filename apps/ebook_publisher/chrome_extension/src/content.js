// 콘텐츠 스크립트: 페이지 입력칸 자동 인식 + 저장된 기본정보로 자동 채우기.
// 안전: 약관 체크/캡차/비밀번호/세금/계좌/제출 버튼은 절대 건드리지 않는다.
(function () {
  "use strict";
  var KW = null;

  function loadKeywords() {
    return fetch(chrome.runtime.getURL("field_keywords.json")).then(function (r) { return r.json(); });
  }

  function labelFor(el) {
    if (el.id) {
      var l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (l) return l.textContent;
    }
    var p = el.closest("label");
    return p ? p.textContent : "";
  }

  function collect() {
    var out = [];
    var nodes = document.querySelectorAll(
      "input, textarea, select, [contenteditable='true']");
    nodes.forEach(function (el) {
      var tag = el.tagName.toLowerCase();
      var type = (el.getAttribute("type") || (tag === "textarea" ? "textarea" : "")).toLowerCase();
      // 비편집/숨김/버튼류 제외
      if (tag === "input" && ["hidden", "submit", "button", "checkbox", "radio", "password"].indexOf(type) !== -1) return;
      if (el.disabled || el.readOnly) return;
      out.push({
        ref: el,
        attrs: {
          tag: tag, type: type,
          name: el.getAttribute("name"), id: el.id,
          placeholder: el.getAttribute("placeholder"),
          aria_label: el.getAttribute("aria-label"),
          label: labelFor(el),
          data_test: el.getAttribute("data-testid")
        }
      });
    });
    return out;
  }

  function setValue(el, value) {
    var tag = el.tagName.toLowerCase();
    if (el.isContentEditable) { el.textContent = value; }
    else if (tag === "select") {
      var opt = Array.prototype.find.call(el.options, function (o) {
        return o.textContent.trim() === value || o.value === value;
      });
      if (opt) el.value = opt.value; else return false;
    } else { el.value = value; }
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function runFill() {
    return new Promise(function (resolve) {
      chrome.storage.local.get("oces_profile", function (data) {
        var profile = data.oces_profile || {};
        var plan = window.OCESFieldMatch.buildFillPlan(profile, collect(), KW);
        var filled = [], manual = [], skipped = [];
        plan.forEach(function (step) {
          if (step.kind === "fill") {
            if (setValue(step.ref, step.value)) {
              filled.push(step.field_key);
              highlight(step.ref, "#d1fae5");
            } else { skipped.push(step.field_key); }
          } else if (step.kind === "file_manual") {
            manual.push(step.field_key);
            highlight(step.ref, "#fef3c7");
          }
        });
        resolve({ filled: filled, manual: manual, skipped: skipped });
      });
    });
  }

  function highlight(el, color) {
    try { el.style.outline = "2px solid " + color; el.style.transition = "outline .3s"; } catch (e) {}
  }

  // 플로팅 버튼 + 결과 패널
  function ui() {
    if (document.getElementById("oces-fab")) return;
    var fab = document.createElement("button");
    fab.id = "oces-fab"; fab.textContent = "📚 자동 채우기";
    fab.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:2147483647;" +
      "background:#111;color:#fff;border:none;border-radius:24px;padding:10px 16px;" +
      "font-size:14px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.3)";
    fab.onclick = function () {
      runFill().then(function (r) {
        showPanel(r);
      });
    };
    document.documentElement.appendChild(fab);
  }

  function showPanel(r) {
    var old = document.getElementById("oces-panel"); if (old) old.remove();
    var box = document.createElement("div");
    box.id = "oces-panel";
    box.style.cssText = "position:fixed;right:16px;bottom:64px;z-index:2147483647;" +
      "background:#fff;color:#111;border:1px solid #ddd;border-radius:10px;padding:12px 14px;" +
      "font-size:13px;max-width:320px;box-shadow:0 4px 16px rgba(0,0,0,.2);line-height:1.6";
    box.innerHTML =
      "<b>자동 채움 결과</b><br>" +
      "✅ 채움: " + (r.filled.join(", ") || "없음") + "<br>" +
      "📎 직접 첨부 필요: " + (r.manual.join(", ") || "없음") + "<br>" +
      "<span style='color:#b45309'>※ 약관 동의·본인인증·세금·최종 게시 버튼은 직접 확인/클릭하세요.</span>";
    document.documentElement.appendChild(box);
    setTimeout(function () { box.remove(); }, 8000);
  }

  // 팝업/단축키에서 오는 실행 메시지
  chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
    if (msg && msg.type === "OCES_FILL") {
      runFill().then(function (r) { showPanel(r); sendResponse(r); });
      return true; // async
    }
  });

  loadKeywords().then(function (kw) { KW = kw; ui(); });
})();
