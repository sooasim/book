import argparse
import csv
import json
from pathlib import Path


REQUIRED_BOOK_FIELDS = [
    "book_id",
    "title",
    "author",
    "language",
    "description",
    "keywords",
    "manuscript_path",
    "cover_path",
    "format",
]


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def check_path(base_dir, value):
    if not value:
        return {"value": value, "exists": False, "reason": "empty"}
    p = Path(value)
    if not p.is_absolute():
        p = base_dir / p
    return {"value": str(p), "exists": p.exists(), "reason": "ok" if p.exists() else "missing"}


def validate_book(book, base_dir):
    missing = [field for field in REQUIRED_BOOK_FIELDS if not book.get(field)]
    manuscript = check_path(base_dir, book.get("manuscript_path", ""))
    cover = check_path(base_dir, book.get("cover_path", ""))
    sample = check_path(base_dir, book.get("sample_path", "")) if book.get("sample_path") else None
    return {
        "missing_required_fields": missing,
        "manuscript": manuscript,
        "cover": cover,
        "sample": sample,
    }


def checklist_for(platform, book, validation):
    items = [
        "계정/출판자 프로필 준비",
        "세금/정산 정보 확인",
        "제목, 부제, 저자명, 출판일 확인",
        "책 소개문과 짧은 소개문 확인",
        "키워드와 카테고리 확인",
        "원고 파일 업로드 전 미리보기 확인",
        "표지 파일과 메타데이터 일치 확인",
        "가격과 권리지역 확인",
        "AI 사용 고지 및 콘텐츠 정책 확인",
        "최종 제출 전 사람이 마지막으로 검토",
    ]

    if platform["platform_id"] == "amazon_kdp":
        items.append("KDP Select 독점 여부 확인")
        items.append("eBook ISBN 미필수, 종이책 ISBN 별도 확인")
    if platform["region"] == "kr":
        items.append("출판사/사업자/ISBN/거래계약 필요 여부 확인")
        items.append("국내 담당자 제출용 사업자 정보와 통장 사본 준비")
    if platform["entry_type"] == "aggregator":
        items.append("중복 유통 방지를 위해 이미 직접 등록한 스토어 제외")

    return {
        "platform": platform,
        "book": book,
        "validation": validation,
        "checklist": items,
    }


def write_markdown(path, package):
    platform = package["platform"]
    book = package["book"]
    validation = package["validation"]

    lines = [
        f"# {book['title']} - {platform['platform_name']} 제출팩",
        "",
        "## 기본 정보",
        "",
        f"- 책 ID: `{book['book_id']}`",
        f"- 제목: {book['title']}",
        f"- 저자: {book.get('author', '')}",
        f"- 언어: {book.get('language', '')}",
        f"- 형식: {book.get('format', '')}",
        f"- 가격: KRW {book.get('price_krw', '')} / USD {book.get('price_usd', '')}",
        f"- 권리지역: {book.get('rights_territories', '')}",
        "",
        "## 파일 확인",
        "",
        f"- 원고: {validation['manuscript']['value']} ({validation['manuscript']['reason']})",
        f"- 표지: {validation['cover']['value']} ({validation['cover']['reason']})",
    ]

    if validation.get("sample"):
        lines.append(f"- 샘플: {validation['sample']['value']} ({validation['sample']['reason']})")

    lines.extend([
        "",
        "## 플랫폼 등록 경로",
        "",
        f"- 플랫폼: {platform['platform_name']}",
        f"- URL: {platform['primary_url']}",
        f"- 자동화 수준: {platform['automation_level']}",
        f"- 권장 경로: {platform['preferred_route']}",
        f"- 메모: {platform['notes']}",
        "",
        "## 체크리스트",
        "",
    ])

    for item in package["checklist"]:
        lines.append(f"- [ ] {item}")

    if validation["missing_required_fields"]:
        lines.extend(["", "## 누락 필수 항목", ""])
        for field in validation["missing_required_fields"]:
            lines.append(f"- {field}")

    lines.extend([
        "",
        "## 소개문",
        "",
        book.get("description", ""),
        "",
        "## 키워드",
        "",
        book.get("keywords", ""),
    ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate ebook platform submission packs.")
    parser.add_argument("--books", required=True, help="Book metadata CSV path")
    parser.add_argument("--platforms", required=True, help="Platform registry CSV path")
    parser.add_argument("--out", required=True, help="Output directory")
    args = parser.parse_args()

    books_path = Path(args.books).resolve()
    platforms_path = Path(args.platforms).resolve()
    out_dir = Path(args.out).resolve()
    base_dir = books_path.parent.parent

    books = read_csv(books_path)
    platforms = read_csv(platforms_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for book in books:
        validation = validate_book(book, base_dir)
        book_dir = out_dir / book["book_id"]
        book_dir.mkdir(parents=True, exist_ok=True)

        for platform in platforms:
            package = checklist_for(platform, book, validation)
            platform_id = platform["platform_id"]
            json_path = book_dir / f"{platform_id}.json"
            md_path = book_dir / f"{platform_id}.md"
            json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
            write_markdown(md_path, package)
            manifest.append({
                "book_id": book["book_id"],
                "platform_id": platform_id,
                "markdown": str(md_path),
                "json": str(json_path),
            })

    manifest_path = out_dir / "submission_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(manifest)} submission packs at {out_dir}")


if __name__ == "__main__":
    main()
