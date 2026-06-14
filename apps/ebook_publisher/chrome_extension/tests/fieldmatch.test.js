// node 내장 모듈만 사용. 실행: node tests/fieldmatch.test.js
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const fm = require("../src/fieldmatch.js");
const KW = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "field_keywords.json"), "utf-8"));

let pass = 0;
function t(name, fn) { fn(); pass++; console.log("  ok -", name); }

t("제목 인식 (한/영)", () => {
  assert.strictEqual(fm.guessFieldKey({ tag: "input", name: "title" }, KW), "title");
  assert.strictEqual(fm.guessFieldKey({ tag: "input", placeholder: "제목" }, KW), "title");
});

t("소개/설명 인식", () => {
  assert.strictEqual(
    fm.guessFieldKey({ tag: "textarea", id: "book_description", label: "책소개" }, KW),
    "description");
});

t("가격 인식", () => {
  assert.strictEqual(fm.guessFieldKey({ tag: "input", name: "가격" }, KW), "price");
});

t("파일 입력 인식", () => {
  assert.strictEqual(
    fm.guessFieldKey({ tag: "input", type: "file", name: "cover-image" }, KW), "cover_file");
});

t("민감 필드는 절대 채우지 않음(null)", () => {
  assert.strictEqual(fm.guessFieldKey({ tag: "input", type: "password", name: "pw" }, KW), null);
  assert.strictEqual(fm.guessFieldKey({ tag: "input", name: "사업자등록번호" }, KW), null);
  assert.strictEqual(fm.guessFieldKey({ tag: "input", name: "card-number" }, KW), null);
  assert.strictEqual(fm.guessFieldKey({ tag: "input", name: "captcha" }, KW), null);
});

t("매칭 없으면 null", () => {
  assert.strictEqual(fm.guessFieldKey({ tag: "input", name: "xyzzy" }, KW), null);
});

t("buildFillPlan: 프로필 값으로 채움, 파일은 수동, 같은키 1회", () => {
  const profile = { title: "제로존", description: "소개", price_krw: "12000",
                    keywords: ["a", "b"] };
  const desc = [
    { ref: 1, attrs: { tag: "input", id: "title", name: "title" } },
    { ref: 2, attrs: { tag: "input", id: "title2", name: "title" } }, // 중복 title
    { ref: 3, attrs: { tag: "textarea", id: "desc", placeholder: "설명" } },
    { ref: 4, attrs: { tag: "input", name: "가격" } },
    { ref: 5, attrs: { tag: "input", name: "keyword" } },
    { ref: 6, attrs: { tag: "input", type: "file", name: "manuscript" } },
    { ref: 7, attrs: { tag: "input", type: "password", name: "pw" } }, // 민감 → 제외
  ];
  const plan = fm.buildFillPlan(profile, desc, KW);
  const byKey = {}; plan.forEach(p => { byKey[p.field_key] = p; });
  assert.strictEqual(byKey.title.value, "제로존");
  assert.strictEqual(byKey.title.ref, 1);              // 첫 요소만
  assert.strictEqual(byKey.price.value, "12000");      // price_krw 별칭
  assert.strictEqual(byKey.keywords.value, "a, b");    // 배열 → 문자열
  assert.strictEqual(byKey.manuscript_file.kind, "file_manual");
  assert.ok(!("password" in byKey));                   // 민감 필드 미포함
  assert.ok(plan.filter(p => p.field_key === "title").length === 1);
});

t("classifyButton: 최종 게시 버튼은 final(클릭 금지)", () => {
  ["출판하기", "게시", "제출", "발행", "Publish", "Submit for review", "등록 완료"].forEach((x) => {
    assert.strictEqual(fm.classifyButton(x, KW), "final", x);
  });
});

t("classifyButton: 저장/다음은 safe", () => {
  ["임시저장", "저장", "다음", "계속", "Save draft", "Next"].forEach((x) => {
    assert.strictEqual(fm.classifyButton(x, KW), "safe", x);
  });
});

t("classifyButton: 최종 키워드 우선(안전 우선)", () => {
  // '최종 저장'처럼 섞여도 final 로 분류되어 자동 클릭 안 됨
  assert.strictEqual(fm.classifyButton("최종 저장", KW), "final");
  assert.strictEqual(fm.classifyButton("", KW), "other");
});

t("resolveOverrides: host 부분일치", () => {
  const ov = { "bookk.co.kr": { title: { by: "name", selector: "book_title" } } };
  assert.deepStrictEqual(fm.resolveOverrides("www.bookk.co.kr", ov).title,
    { by: "name", selector: "book_title" });
  assert.deepStrictEqual(fm.resolveOverrides("example.com", ov), {});
});

console.log(`\nfieldmatch.test.js: ${pass} passed`);
