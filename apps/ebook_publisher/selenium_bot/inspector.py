"""사이트 구조 자동 파악 — 게시 페이지의 입력 폼을 탐지해 필드 매핑을 학습한다.

흐름:
  1) inspect_fields(driver): 현재 열린 페이지의 input/textarea/select 요소 속성을 수집.
  2) propose_mapping(descriptors): 속성(name/id/placeholder/label/type)을 한국어·영어
     키워드 사전과 대조해 우리 표준 field_key 로 매핑(휴리스틱).
  3) learn_mapping(platform_id, driver, store): 1+2 를 수행해 mappings/{platform}.json 에 저장.

휴리스틱(guess_field_key, build_selector, propose_mapping)은 순수 함수라 selenium 없이 테스트된다.
"""
from __future__ import annotations

from .field_mapping import MappingStore
from .models import FieldSelector

# 표준 field_key -> (키워드들). 한국어/영어 모두 포함. 소문자 부분일치.
FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "title": ("title", "book title", "제목", "도서명", "책제목"),
    "subtitle": ("subtitle", "부제"),
    "author": ("author", "writer", "byline", "저자", "지은이", "작가"),
    "description": ("description", "synopsis", "summary", "about", "book description",
                    "소개", "설명", "책소개", "줄거리", "상세"),
    "short_description": ("short description", "tagline", "blurb", "한줄", "짧은소개"),
    "keywords": ("keyword", "tags", "search terms", "키워드", "태그", "검색어"),
    "categories": ("category", "genre", "categories", "카테고리", "장르", "분야"),
    "language": ("language", "언어"),
    "price": ("price", "list price", "amount", "가격", "정가", "판매가"),
    "isbn": ("isbn",),
    "manuscript_file": ("manuscript", "ebook file", "epub", "upload book", "content file",
                        "원고", "본문파일", "파일업로드", "도서파일"),
    "cover_file": ("cover", "thumbnail", "book cover", "표지", "커버", "썸네일"),
}

# 우선순위: 명시적 파일 입력은 type=file 로 우선 판정
FILE_FIELD_KEYS = ("manuscript_file", "cover_file")


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def guess_field_key(attrs: dict) -> str | None:
    """입력 요소 속성으로 표준 field_key 추정. 매칭 없으면 None.

    attrs 예: {"tag":"input","type":"text","name":"book[title]","id":"title",
              "placeholder":"제목","aria_label":"","label":"책 제목"}
    """
    tag = _norm(attrs.get("tag"))
    itype = _norm(attrs.get("type"))
    haystack = " ".join(_norm(attrs.get(k)) for k in
                        ("name", "id", "placeholder", "aria_label", "label", "data_test"))

    # 파일 입력 우선 판정
    if itype == "file" or tag == "input" and itype == "file":
        for key in FILE_FIELD_KEYS:
            if any(kw in haystack for kw in FIELD_KEYWORDS[key]):
                return key
        # 파일인데 단서 없으면 원고로 가정하지 않고 None(사람이 지정)
        return None

    # 일반 텍스트/선택 필드: 키워드 점수 최댓값
    best, best_score = None, 0
    for key, kws in FIELD_KEYWORDS.items():
        if key in FILE_FIELD_KEYS:
            continue
        score = sum(1 for kw in kws if kw in haystack)
        # 더 긴(구체적) 키워드 매칭에 가중치
        score += sum(len(kw) for kw in kws if kw in haystack) / 100.0
        if score > best_score:
            best, best_score = key, score
    return best if best_score > 0 else None


def build_selector(attrs: dict) -> FieldSelector | None:
    """요소 속성으로 가장 안정적인 셀렉터 생성(id > name > css)."""
    field_type = "file" if _norm(attrs.get("type")) == "file" else (
        "textarea" if _norm(attrs.get("tag")) == "textarea" else
        "select" if _norm(attrs.get("tag")) == "select" else "text")
    el_id = attrs.get("id")
    name = attrs.get("name")
    if el_id:
        return FieldSelector(field_key="", by="id", selector=el_id, field_type=field_type)
    if name:
        return FieldSelector(field_key="", by="name", selector=name, field_type=field_type)
    css = attrs.get("css")
    if css:
        return FieldSelector(field_key="", by="css", selector=css, field_type=field_type)
    return None


def propose_mapping(descriptors: list[dict]) -> dict[str, FieldSelector]:
    """탐지된 요소 목록 → {field_key: FieldSelector}. 같은 키 중복 시 먼저 나온 것 유지."""
    mapping: dict[str, FieldSelector] = {}
    for attrs in descriptors:
        key = guess_field_key(attrs)
        if not key or key in mapping:
            continue
        sel = build_selector(attrs)
        if sel is None:
            continue
        sel.field_key = key
        mapping[key] = sel
    return mapping


# ---------------------------------------------------------------- 드라이버 연동(런타임)
def inspect_fields(driver) -> list[dict]:
    """현재 페이지의 input/textarea/select 요소 속성을 수집(selenium 런타임)."""
    from .driver import by_method
    descriptors: list[dict] = []
    for tag in ("input", "textarea", "select"):
        for el in driver.find_elements(by_method("css"), tag):
            try:
                descriptors.append({
                    "tag": tag,
                    "type": el.get_attribute("type"),
                    "name": el.get_attribute("name"),
                    "id": el.get_attribute("id"),
                    "placeholder": el.get_attribute("placeholder"),
                    "aria_label": el.get_attribute("aria-label"),
                    "data_test": el.get_attribute("data-testid"),
                })
            except Exception:
                continue
    return descriptors


def learn_mapping(platform_id: str, driver, store: MappingStore | None = None) -> dict:
    """페이지를 스캔해 매핑을 제안하고 저장. 저장된 field_key 목록과 미탐지 키 반환."""
    store = store or MappingStore()
    descriptors = inspect_fields(driver)
    proposal = propose_mapping(descriptors)
    for key, sel in proposal.items():
        store.set_field(platform_id, key, sel.by, sel.selector, sel.field_type)
    from .field_mapping import DEFAULT_FIELD_KEYS
    found = sorted(proposal.keys())
    missing = [k for k in DEFAULT_FIELD_KEYS if k not in proposal]
    return {"platform_id": platform_id, "detected": len(descriptors),
            "mapped": found, "missing": missing}
