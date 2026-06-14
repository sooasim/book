// 필드 자동 인식 + 채우기 계획 (순수 로직, DOM 비의존 — node 테스트 가능).
// inspector.py 의 휴리스틱을 이식. field_keywords.json 을 단일 소스로 사용.
(function (root) {
  "use strict";

  function norm(s) { return (s == null ? "" : String(s)).trim().toLowerCase(); }

  // attrs: {tag,type,name,id,placeholder,aria_label,label,data_test}
  function haystack(attrs) {
    return ["name", "id", "placeholder", "aria_label", "label", "data_test"]
      .map(function (k) { return norm(attrs[k]); }).join(" ");
  }

  function isSensitive(attrs, kw) {
    var hay = haystack(attrs) + " " + norm(attrs.type);
    return kw.sensitive.some(function (w) { return hay.indexOf(w) !== -1; });
  }

  // 표준 field_key 추정. 매칭 없으면 null. (kw = field_keywords.json)
  function guessFieldKey(attrs, kw) {
    var tag = norm(attrs.tag), itype = norm(attrs.type);
    // 민감 필드는 절대 채우지 않음
    if (isSensitive(attrs, kw)) return null;
    var hay = haystack(attrs);
    // 파일 입력: 파일 키만 매칭
    if (itype === "file") {
      for (var i = 0; i < kw.file_fields.length; i++) {
        var fk = kw.file_fields[i];
        if ((kw.fields[fk] || []).some(function (w) { return hay.indexOf(w) !== -1; })) return fk;
      }
      return null;
    }
    var best = null, bestScore = 0;
    Object.keys(kw.fields).forEach(function (key) {
      if (kw.file_fields.indexOf(key) !== -1) return;
      var kws = kw.fields[key], score = 0;
      kws.forEach(function (w) {
        if (hay.indexOf(w) !== -1) { score += 1 + w.length / 100.0; }
      });
      if (score > bestScore) { best = key; bestScore = score; }
    });
    return bestScore > 0 ? best : null;
  }

  // profile(저장된 기본정보) + 인식된 필드 → 채우기 계획.
  // 반환: [{field_key, value, kind:"fill"|"file_manual"|"skip", reason}]
  function buildFillPlan(profile, descriptors, kw) {
    var plan = [];
    var used = {};
    descriptors.forEach(function (d) {
      var key = guessFieldKey(d.attrs, kw);
      if (!key) { return; }
      if (used[key]) { return; }           // 같은 키는 첫 요소만
      // 파일 입력은 브라우저 보안상 확장이 값 설정 불가 → 사람이 첨부
      if (kw.file_fields.indexOf(key) !== -1) {
        used[key] = true;
        plan.push({ field_key: key, ref: d.ref, kind: "file_manual",
                    reason: "파일은 직접 첨부(브라우저 보안)" });
        return;
      }
      var value = profileValue(profile, key);
      if (value == null || value === "") { return; }
      used[key] = true;
      plan.push({ field_key: key, ref: d.ref, value: value, kind: "fill" });
    });
    return plan;
  }

  // 저장 프로필에서 field_key 에 해당하는 값 추출(키 별칭 처리).
  function profileValue(p, key) {
    if (!p) return "";
    if (key === "price") return p.price || p.price_krw || p.price_usd || "";
    if (key === "keywords") {
      var k = p.keywords;
      return Array.isArray(k) ? k.join(", ") : (k || "");
    }
    if (key === "categories") {
      var c = p.categories;
      return Array.isArray(c) ? c.join(", ") : (c || "");
    }
    if (key === "isbn") return p.isbn || p.isbn_ebook || "";
    return p[key] != null ? p[key] : "";
  }

  var api = { norm: norm, isSensitive: isSensitive, guessFieldKey: guessFieldKey,
              buildFillPlan: buildFillPlan, profileValue: profileValue };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; }
  else { root.OCESFieldMatch = api; }
})(typeof window !== "undefined" ? window : this);
