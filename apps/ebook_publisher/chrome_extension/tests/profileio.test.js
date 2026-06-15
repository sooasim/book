// 실행: node tests/profileio.test.js
const assert = require("assert");
const io = require("../src/profileio.js");
let pass = 0;
function t(n, f) { f(); pass++; console.log("  ok -", n); }

t("허용 키만 통과, 민감 키 제거", () => {
  const c = io.normalizeProfile({
    title: "제로존", author: "ATA", password: "x", tax_id: "123",
    계좌: "999", description: "소개"
  });
  assert.strictEqual(c.title, "제로존");
  assert.strictEqual(c.description, "소개");
  assert.ok(!("password" in c));
  assert.ok(!("tax_id" in c));
  assert.ok(!("계좌" in c));
});

t("keywords 문자열 → 배열", () => {
  const c = io.normalizeProfile({ title: "t", keywords: "수학, 철학 , 제로존" });
  assert.deepStrictEqual(c.keywords, ["수학", "철학", "제로존"]);
});

t("keywords 배열 유지", () => {
  const c = io.normalizeProfile({ title: "t", categories: ["과학", "수학"] });
  assert.deepStrictEqual(c.categories, ["과학", "수학"]);
});

t("parseImport: 정상 JSON", () => {
  const c = io.parseImport('{"title":"제로존","author":"ATA","price_usd":"9.99"}');
  assert.strictEqual(c.title, "제로존");
  assert.strictEqual(c.price_usd, "9.99");
});

t("parseImport: 잘못된 JSON → 예외", () => {
  assert.throws(() => io.parseImport("{not json"));
});

t("parseImport: 유효 필드 없음 → 예외", () => {
  assert.throws(() => io.parseImport('{"password":"x","random":"y"}'));
});

console.log(`\nprofileio.test.js: ${pass} passed`);
