// 프로필 입출력(순수 로직, node 테스트 가능).
// 스튜디오가 내보낸 JSON 을 확장 기본정보(oces_profile)로 안전하게 정규화.
(function (root) {
  "use strict";

  // 확장이 저장/사용하는 허용 키만 통과.
  var ALLOWED = ["title", "subtitle", "author", "pen_name", "language",
    "short_description", "description", "keywords", "categories",
    "price_krw", "price_usd", "isbn_ebook"];

  // 민감 단서가 들어간 키는 절대 저장하지 않는다.
  var SENSITIVE = ["password", "passwd", "pwd", "비밀번호", "암호", "tax", "세금",
    "card", "카드", "account", "계좌", "ssn", "주민", "사업자", "token", "secret",
    "payout", "정산", "vat"];

  function isSensitiveKey(k) {
    var s = String(k).toLowerCase();
    return SENSITIVE.some(function (w) { return s.indexOf(w) !== -1; });
  }

  // 입력 객체 → 허용 키만, 민감 키 제거, keywords/categories 정규화.
  function normalizeProfile(obj) {
    var out = {};
    if (!obj || typeof obj !== "object") return out;
    ALLOWED.forEach(function (k) {
      if (isSensitiveKey(k)) return;
      if (!(k in obj)) return;
      var v = obj[k];
      if (v == null || v === "") return;
      if (k === "keywords" || k === "categories") {
        if (Array.isArray(v)) out[k] = v.map(String).map(function (s) { return s.trim(); }).filter(Boolean);
        else out[k] = String(v).split(",").map(function (s) { return s.trim(); }).filter(Boolean);
      } else {
        out[k] = String(v);
      }
    });
    return out;
  }

  // JSON 문자열 파싱 → 정규화. 실패 시 throw.
  function parseImport(text) {
    var obj = JSON.parse(text);            // 잘못된 JSON 이면 예외
    var clean = normalizeProfile(obj);
    if (Object.keys(clean).length === 0) {
      throw new Error("가져올 수 있는 기본정보 필드가 없습니다.");
    }
    return clean;
  }

  var api = { ALLOWED: ALLOWED, isSensitiveKey: isSensitiveKey,
              normalizeProfile: normalizeProfile, parseImport: parseImport };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.OCESProfileIO = api;
})(typeof window !== "undefined" ? window : this);
