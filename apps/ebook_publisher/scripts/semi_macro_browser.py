import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOKS = ROOT / "book_metadata_template.csv"
DEFAULT_PLATFORMS = ROOT / "platform_registry.csv"
DEFAULT_PROFILE = ROOT / "publisher_profile_template.csv"
DEFAULT_MAPPING_DIR = ROOT / "mappings"
DEFAULT_BROWSER_PROFILE = ROOT / ".chromium_profile"


CANONICAL_FIELDS = {
    "title": ["title", "book title", "제목", "도서명", "상품명", "책 제목"],
    "subtitle": ["subtitle", "sub title", "부제", "부제목"],
    "author": ["author", "contributor", "저자", "작가", "필자", "creator"],
    "pen_name": ["pen name", "필명"],
    "description": ["description", "book description", "synopsis", "소개", "책소개", "상세 설명", "상세소개", "도서 소개"],
    "short_description": ["short description", "summary", "요약", "짧은 소개", "간단 소개"],
    "keywords": ["keyword", "keywords", "search terms", "검색어", "키워드", "태그"],
    "categories": ["category", "categories", "genre", "카테고리", "분야", "장르"],
    "language": ["language", "언어"],
    "isbn_ebook": ["isbn", "isbn13", "ebook isbn", "전자책 isbn"],
    "publication_date": ["publication date", "release date", "출간일", "발행일", "출시일"],
    "price_krw": ["krw", "won", "price", "list price", "원화", "가격", "판매가", "정가"],
    "price_usd": ["usd", "dollar", "price", "list price", "달러"],
    "rights_territories": ["territory", "territories", "rights", "권리", "판매지역", "권리지역"],
    "manuscript_path": ["manuscript", "interior", "book file", "원고", "본문", "파일 업로드", "도서 파일"],
    "cover_path": ["cover", "cover image", "표지", "커버", "이미지"],
    "publisher_name": ["publisher", "출판사", "브랜드", "회사명"],
    "legal_name": ["legal name", "대표자", "성명", "이름"],
    "email": ["email", "e-mail", "이메일", "메일"],
    "phone": ["phone", "mobile", "전화", "휴대폰", "연락처"],
    "address_line1": ["address", "주소"],
    "postal_code": ["postal", "zip", "우편번호"],
    "website": ["website", "url", "홈페이지", "웹사이트"],
}


BLOCKED_INPUT_TYPES = {"password", "hidden", "submit", "button", "reset", "checkbox", "radio"}
FILE_FIELDS = {"manuscript_path", "cover_path", "sample_path"}
HUMAN_GATE_WORDS = [
    "captcha",
    "recaptcha",
    "본인인증",
    "휴대폰 인증",
    "약관",
    "동의",
    "submit",
    "publish",
    "출판",
    "제출",
    "등록 완료",
    "결제",
    "세금",
    "정산",
    "계좌",
]


@dataclass
class FillResult:
    selector: str
    field: str
    value_preview: str
    confidence: float
    status: str
    reason: str = ""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_key_value_csv(path: Path) -> dict[str, str]:
    rows = read_csv_rows(path)
    out: dict[str, str] = {}
    for row in rows:
        key = (row.get("field") or "").strip()
        if key:
            out[key] = (row.get("value") or "").strip()
    return out


def load_book(book_id: str, books_path: Path) -> dict[str, str]:
    rows = read_csv_rows(books_path)
    for row in rows:
        if row.get("book_id") == book_id:
            return {k: (v or "").strip() for k, v in row.items()}
    raise SystemExit(f"book_id를 찾을 수 없습니다: {book_id}")


def load_platform(platform_id: str, platforms_path: Path) -> dict[str, str]:
    rows = read_csv_rows(platforms_path)
    for row in rows:
        if row.get("platform_id") == platform_id:
            return {k: (v or "").strip() for k, v in row.items()}
    raise SystemExit(f"platform_id를 찾을 수 없습니다: {platform_id}")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def score_field(candidate_text: str, canonical_field: str) -> float:
    text = normalize_text(candidate_text)
    if not text:
        return 0.0
    best = 0.0
    for token in CANONICAL_FIELDS.get(canonical_field, []):
        t = normalize_text(token)
        if not t:
            continue
        if text == t:
            best = max(best, 1.0)
        elif t in text:
            best = max(best, 0.86 if len(t) >= 3 else 0.5)
        else:
            token_parts = [p for p in re.split(r"[\s/_-]+", t) if p]
            if token_parts and all(part in text for part in token_parts):
                best = max(best, 0.72)
    return best


def infer_field(candidate: dict[str, Any], available_values: dict[str, str]) -> tuple[str | None, float]:
    primary_text = " ".join(
        str(candidate.get(key, ""))
        for key in ["label", "aria", "placeholder", "name", "id"]
    )
    nearby_text = str(candidate.get("nearby", ""))
    primary_norm = normalize_text(primary_text)
    priority_rules = [
        ("subtitle", ["subtitle", "sub title", "부제", "부제목"]),
        ("isbn_ebook", ["isbn", "isbn13"]),
        ("price_krw", ["price_krw", "원화", "krw", "won"]),
        ("price_usd", ["price_usd", "usd", "dollar", "달러"]),
        ("manuscript_path", ["manuscript", "interior", "원고", "본문"]),
        ("cover_path", ["cover", "표지", "커버"]),
    ]
    for field, tokens in priority_rules:
        if available_values.get(field) and any(normalize_text(token) in primary_norm for token in tokens):
            return field, 0.94

    best_field = None
    best_score = 0.0
    for field, value in available_values.items():
        if not value:
            continue
        primary_score = score_field(primary_text, field)
        nearby_score = score_field(nearby_text, field) * 0.35
        score = max(primary_score, nearby_score)
        if score > best_score:
            best_field = field
            best_score = score
    return best_field, best_score


def value_preview(value: str) -> str:
    clean = re.sub(r"\s+", " ", value or "").strip()
    if len(clean) <= 42:
        return clean
    return clean[:39] + "..."


def build_values(book: dict[str, str], profile: dict[str, str]) -> dict[str, str]:
    values = dict(profile)
    values.update(book)
    if values.get("keywords"):
        values["keywords"] = values["keywords"].replace(";", ", ")
    if values.get("categories"):
        values["categories"] = values["categories"].replace(";", ", ")
    return {k: v for k, v in values.items() if v}


def resolve_file_path(value: str, base_dir: Path) -> str:
    p = Path(value)
    if not p.is_absolute():
        p = base_dir / p
    return str(p.resolve())


def mapping_path(mapping_dir: Path, platform_id: str) -> Path:
    return mapping_dir / f"{platform_id}.json"


def load_mapping(mapping_dir: Path, platform_id: str) -> dict[str, Any]:
    path = mapping_path(mapping_dir, platform_id)
    if not path.exists():
        return {"platform_id": platform_id, "fields": {}, "learned_urls": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_mapping(mapping_dir: Path, platform_id: str, mapping: dict[str, Any]) -> None:
    mapping_dir.mkdir(parents=True, exist_ok=True)
    path = mapping_path(mapping_dir, platform_id)
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")


def scan_page(page) -> list[dict[str, Any]]:
    return page.evaluate(
        """
        () => {
          const visible = (el) => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
          };
          const labelText = (el) => {
            const texts = [];
            if (el.id) {
              const lab = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
              if (lab) texts.push(lab.innerText || lab.textContent || '');
            }
            const parentLabel = el.closest('label');
            if (parentLabel) texts.push(parentLabel.innerText || parentLabel.textContent || '');
            const ariaLabelledBy = el.getAttribute('aria-labelledby');
            if (ariaLabelledBy) {
              ariaLabelledBy.split(/\\s+/).forEach((id) => {
                const node = document.getElementById(id);
                if (node) texts.push(node.innerText || node.textContent || '');
              });
            }
            return texts.join(' ').replace(/\\s+/g, ' ').trim();
          };
          const nearbyText = (el) => {
            const texts = [];
            let node = el.parentElement;
            for (let i = 0; node && i < 3; i += 1, node = node.parentElement) {
              const cloned = node.cloneNode(true);
              cloned.querySelectorAll('input, textarea, select, button, script, style').forEach((n) => n.remove());
              texts.push(cloned.innerText || cloned.textContent || '');
            }
            return texts.join(' ').replace(/\\s+/g, ' ').trim().slice(0, 500);
          };
          const cssPath = (el) => {
            if (el.id) return `#${CSS.escape(el.id)}`;
            const name = el.getAttribute('name');
            if (name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
            const parts = [];
            let node = el;
            while (node && node.nodeType === Node.ELEMENT_NODE && parts.length < 5) {
              let part = node.tagName.toLowerCase();
              const parent = node.parentElement;
              if (parent) {
                const same = Array.from(parent.children).filter((child) => child.tagName === node.tagName);
                if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
              }
              parts.unshift(part);
              node = parent;
            }
            return parts.join(' > ');
          };
          const nodes = Array.from(document.querySelectorAll('input, textarea, select, [contenteditable="true"]'));
          return nodes.filter(visible).map((el, index) => ({
            index,
            selector: cssPath(el),
            tag: el.tagName.toLowerCase(),
            type: (el.getAttribute('type') || '').toLowerCase(),
            name: el.getAttribute('name') || '',
            id: el.id || '',
            aria: el.getAttribute('aria-label') || '',
            placeholder: el.getAttribute('placeholder') || '',
            label: labelText(el),
            nearby: nearbyText(el),
            value: el.value || el.innerText || ''
          }));
        }
        """
    )


def detect_human_gates(page) -> list[str]:
    text = normalize_text(page.locator("body").inner_text(timeout=3000)[:5000])
    return [word for word in HUMAN_GATE_WORDS if normalize_text(word) in text]


def fill_selector(page, selector: str, field: str, value: str, base_dir: Path, dry_run: bool) -> FillResult:
    preview = value_preview(value)
    if dry_run:
        return FillResult(selector, field, preview, 1.0, "dry_run")
    try:
        locator = page.locator(selector).first
        element_info = locator.evaluate(
            "(el) => ({tag: el.tagName.toLowerCase(), type: (el.getAttribute('type') || '').toLowerCase(), contenteditable: el.isContentEditable})"
        )
        if element_info["type"] in BLOCKED_INPUT_TYPES:
            return FillResult(selector, field, preview, 1.0, "skipped", f"blocked input type: {element_info['type']}")
        if field in FILE_FIELDS or element_info["type"] == "file":
            file_path = resolve_file_path(value, base_dir)
            if not Path(file_path).exists():
                return FillResult(selector, field, preview, 1.0, "failed", f"file missing: {file_path}")
            locator.set_input_files(file_path)
            return FillResult(selector, field, preview, 1.0, "filled")
        if element_info["tag"] == "select":
            try:
                locator.select_option(label=value)
            except PlaywrightError:
                locator.select_option(value=value)
            return FillResult(selector, field, preview, 1.0, "filled")
        locator.fill(value)
        return FillResult(selector, field, preview, 1.0, "filled")
    except Exception as exc:
        return FillResult(selector, field, preview, 1.0, "failed", str(exc))


def fill_from_mapping(page, mapping: dict[str, Any], values: dict[str, str], base_dir: Path, dry_run: bool) -> list[FillResult]:
    results: list[FillResult] = []
    for field, info in mapping.get("fields", {}).items():
        value = values.get(field, "")
        selector = info.get("selector", "")
        if not value or not selector:
            continue
        results.append(fill_selector(page, selector, field, value, base_dir, dry_run))
    return results


def fill_from_scan(
    page,
    candidates: list[dict[str, Any]],
    values: dict[str, str],
    base_dir: Path,
    threshold: float,
    dry_run: bool,
) -> tuple[list[FillResult], dict[str, dict[str, Any]]]:
    used_fields: set[str] = set()
    proposed_mapping: dict[str, dict[str, Any]] = {}
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for candidate in candidates:
        if candidate.get("type") in BLOCKED_INPUT_TYPES:
            continue
        field, score = infer_field(candidate, values)
        if field and score >= threshold:
            scored.append((score, field, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)

    results: list[FillResult] = []
    for score, field, candidate in scored:
        if field in used_fields:
            continue
        value = values.get(field, "")
        if not value:
            continue
        selector = candidate["selector"]
        result = fill_selector(page, selector, field, value, base_dir, dry_run)
        result.confidence = score
        results.append(result)
        used_fields.add(field)
        if result.status in {"filled", "dry_run"}:
            proposed_mapping[field] = {
                "selector": selector,
                "confidence": score,
                "label": candidate.get("label", ""),
                "placeholder": candidate.get("placeholder", ""),
                "name": candidate.get("name", ""),
                "id": candidate.get("id", ""),
            }
    return results, proposed_mapping


def print_candidates(candidates: list[dict[str, Any]], values: dict[str, str]) -> None:
    print("\n[페이지 입력칸 인식 결과]")
    for candidate in candidates:
        field, score = infer_field(candidate, values)
        label = candidate.get("label") or candidate.get("placeholder") or candidate.get("name") or candidate.get("id") or candidate.get("nearby", "")[:60]
        print(f"- #{candidate['index']:02d} selector={candidate['selector']} field={field or '-'} score={score:.2f} label={label[:100]}")


def run(args: argparse.Namespace) -> None:
    books_path = Path(args.books).resolve()
    platforms_path = Path(args.platforms).resolve()
    profile_path = Path(args.profile).resolve()
    mapping_dir = Path(args.mapping_dir).resolve()
    browser_profile = Path(args.browser_profile).resolve()

    book = load_book(args.book_id, books_path)
    platform = load_platform(args.platform, platforms_path)
    profile = read_key_value_csv(profile_path) if profile_path.exists() else {}
    values = build_values(book, profile)
    url = args.url or platform.get("primary_url") or "about:blank"
    mapping = load_mapping(mapping_dir, args.platform)
    base_dir = books_path.parent.parent

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(browser_profile),
            headless=False,
            viewport={"width": 1360, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded")

        print(f"\n[별도 Chromium 열림] {platform.get('platform_name')} - {url}")
        print("로그인, 본인인증, CAPTCHA가 필요하면 브라우저에서 직접 처리하세요.")
        if not args.no_prompt:
            input("입력할 페이지까지 이동한 뒤 Enter를 누르면 페이지를 인식합니다...")

        gates = detect_human_gates(page)
        if gates:
            print(f"\n[사람 확인 게이트 감지] {', '.join(sorted(set(gates)))}")
            print("약관/인증/최종 제출 관련 항목은 자동 처리하지 않습니다.")

        candidates = scan_page(page)
        print_candidates(candidates, values)

        results: list[FillResult] = []
        learned: dict[str, dict[str, Any]] = {}

        if args.mode in {"one-click", "assist"} and mapping.get("fields"):
            print("\n[저장된 학습 매핑으로 입력]")
            results.extend(fill_from_mapping(page, mapping, values, base_dir, args.dry_run))

        if args.mode in {"learn", "assist"}:
            print("\n[페이지 인식 기반 자동 입력]")
            scan_results, learned = fill_from_scan(page, candidates, values, base_dir, args.threshold, args.dry_run)
            results.extend(scan_results)

        if args.mode == "inspect":
            print("\ninspect 모드라 입력하지 않았습니다.")

        if results:
            print("\n[입력 결과]")
            for result in results:
                print(
                    f"- {result.status}: {result.field} -> {result.selector} "
                    f"score={result.confidence:.2f} value={result.value_preview} {result.reason}"
                )

        if learned and args.save_learned and not args.dry_run:
            mapping.setdefault("fields", {}).update(learned)
            mapping.setdefault("learned_urls", [])
            current_url = page.url
            if current_url not in mapping["learned_urls"]:
                mapping["learned_urls"].append(current_url)
            mapping["last_hostname"] = urlparse(current_url).hostname or ""
            save_mapping(mapping_dir, args.platform, mapping)
            print(f"\n[학습 저장] {mapping_path(mapping_dir, args.platform)}")

        print("\n최종 제출, 약관 동의, 독점 선택은 브라우저에서 직접 확인하세요.")
        if not args.no_prompt:
            input("확인 후 Enter를 누르면 Chromium을 닫습니다...")
        elif args.close_delay_ms > 0:
            page.wait_for_timeout(args.close_delay_ms)
        context.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="별도 Chromium으로 전자책 사이트 입력을 보조하는 반매크로 도구")
    parser.add_argument("--platform", required=True, help="platform_registry.csv의 platform_id")
    parser.add_argument("--book-id", required=True, help="book_metadata CSV의 book_id")
    parser.add_argument("--url", help="직접 열 URL. 생략하면 플랫폼 레지스트리 URL 사용")
    parser.add_argument("--mode", choices=["inspect", "learn", "assist", "one-click"], default="assist")
    parser.add_argument("--books", default=str(DEFAULT_BOOKS))
    parser.add_argument("--platforms", default=str(DEFAULT_PLATFORMS))
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--mapping-dir", default=str(DEFAULT_MAPPING_DIR))
    parser.add_argument("--browser-profile", default=str(DEFAULT_BROWSER_PROFILE))
    parser.add_argument("--threshold", type=float, default=0.70, help="자동 입력 최소 신뢰도")
    parser.add_argument("--dry-run", action="store_true", help="입력하지 않고 인식 결과만 확인")
    parser.add_argument("--no-prompt", action="store_true", help="테스트용: Enter 대기 없이 바로 인식 후 종료")
    parser.add_argument("--close-delay-ms", type=int, default=0, help="--no-prompt 사용 시 종료 전 대기 시간")
    parser.add_argument("--no-save-learned", dest="save_learned", action="store_false", help="학습 매핑 저장 안 함")
    parser.set_defaults(save_learned=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
