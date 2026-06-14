// 기본정보 저장/로드 (chrome.storage.local, key=oces_profile)
var FIELDS = ["title", "subtitle", "author", "pen_name", "language",
  "short_description", "description", "keywords", "categories",
  "price_krw", "price_usd", "isbn_ebook"];

function load() {
  chrome.storage.local.get("oces_profile", function (data) {
    var p = data.oces_profile || {};
    FIELDS.forEach(function (k) {
      var el = document.querySelector('[name="' + k + '"]');
      if (!el) return;
      var v = p[k];
      if (Array.isArray(v)) v = v.join(", ");
      el.value = v != null ? v : "";
    });
  });
}

document.getElementById("form").addEventListener("submit", function (e) {
  e.preventDefault();
  var p = {};
  FIELDS.forEach(function (k) {
    var el = document.querySelector('[name="' + k + '"]');
    if (el && el.value.trim() !== "") p[k] = el.value.trim();
  });
  // keywords/categories 는 배열로 정규화
  ["keywords", "categories"].forEach(function (k) {
    if (p[k]) p[k] = p[k].split(",").map(function (s) { return s.trim(); }).filter(Boolean);
  });
  chrome.storage.local.set({ oces_profile: p }, function () {
    var s = document.getElementById("status");
    s.textContent = "✅ 저장됨";
    setTimeout(function () { s.textContent = ""; }, 2000);
  });
});

load();
