import csv
import json
import subprocess
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
UI_PATH = ROOT / "ui" / "one_click_publisher_dashboard.html"
BOOKS_CSV = ROOT / "book_metadata.csv"
PLATFORMS_CSV = ROOT / "platform_registry.csv"
STATUS_CSV = ROOT / "publication_status.csv"
QUEUE_CSV = ROOT / "submission_queue.csv"
TOOLCHAIN_JSON = ROOT / "toolchain_status.json"
OUT_DIR = ROOT / "out"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_check(book: dict[str, str]) -> dict:
    checks = {}
    for key in ["manuscript_path", "cover_path", "sample_path"]:
        value = book.get(key, "")
        if not value:
            checks[key] = {"value": "", "exists": False, "status": "empty"}
            continue
        path = Path(value)
        if not path.is_absolute():
            path = ROOT.parent / value
        checks[key] = {"value": str(path), "exists": path.exists(), "status": "ok" if path.exists() else "missing"}
    return checks


def platform_status_matrix() -> list[dict]:
    books = read_csv(BOOKS_CSV)
    platforms = read_csv(PLATFORMS_CSV)
    statuses = read_csv(STATUS_CSV)
    status_map = {(row.get("book_id"), row.get("platform_id")): row for row in statuses}
    matrix = []
    for book in books:
        book_id = book.get("book_id", "")
        for platform in platforms:
            platform_id = platform.get("platform_id", "")
            status = status_map.get((book_id, platform_id), {})
            matrix.append(
                {
                    "book_id": book_id,
                    "title": book.get("title", ""),
                    "platform_id": platform_id,
                    "platform_name": platform.get("platform_name", ""),
                    "region": platform.get("region", ""),
                    "automation_level": platform.get("automation_level", ""),
                    "status": status.get("status", "not_started"),
                    "next_action": status.get("next_action") or platform.get("preferred_route", ""),
                    "updated_at": status.get("updated_at", ""),
                }
            )
    return matrix


def summary() -> dict:
    books = read_csv(BOOKS_CSV)
    platforms = read_csv(PLATFORMS_CSV)
    statuses = read_csv(STATUS_CSV)
    queues = read_csv(QUEUE_CSV)
    missing_files = 0
    for book in books:
        checks = file_check(book)
        missing_files += sum(1 for key, value in checks.items() if key != "sample_path" and not value["exists"])
    pack_count = len(list(OUT_DIR.glob("*/*.md"))) + len(list(OUT_DIR.glob("*/*.json")))
    human_wait = sum(1 for row in statuses + queues if "human" in " ".join(row.values()).lower() or "확인" in " ".join(row.values()))
    return {
        "books": len(books),
        "platforms": len(platforms),
        "statuses": len(statuses),
        "queue": len(queues),
        "pack_files": pack_count,
        "missing_files": missing_files,
        "human_wait": human_wait,
        "browser_assisted": sum(1 for p in platforms if "browser" in p.get("automation_level", "")),
        "manual_contract": sum(1 for p in platforms if "contract" in p.get("automation_level", "")),
    }


def app_state() -> dict:
    books = read_csv(BOOKS_CSV)
    return {
        "summary": summary(),
        "books": [{**book, "file_check": file_check(book)} for book in books],
        "platforms": read_csv(PLATFORMS_CSV),
        "statuses": read_csv(STATUS_CSV),
        "queue": read_csv(QUEUE_CSV),
        "matrix": platform_status_matrix(),
        "toolchain": read_json(TOOLCHAIN_JSON),
        "paths": {
            "root": str(ROOT),
            "dashboard": str(UI_PATH),
            "books_csv": str(BOOKS_CSV),
            "platforms_csv": str(PLATFORMS_CSV),
            "out_dir": str(OUT_DIR),
        },
    }


def run_command(args: list[str], timeout: int = 120) -> dict:
    proc = subprocess.run(args, cwd=str(ROOT.parent), text=True, capture_output=True, timeout=timeout)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }


def generate_packs() -> dict:
    script = ROOT / "scripts" / "generate_submission_pack.py"
    return run_command(
        [
            sys.executable,
            str(script),
            "--books",
            str(BOOKS_CSV),
            "--platforms",
            str(PLATFORMS_CSV),
            "--out",
            str(OUT_DIR),
        ]
    )


def check_toolchain() -> dict:
    script = ROOT / "scripts" / "check_ebook_toolchain.ps1"
    result = run_command(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)], timeout=60)
    result["toolchain"] = read_json(TOOLCHAIN_JSON)
    return result


def assist_command(book_id: str = "", platform_id: str = "amazon_kdp") -> dict:
    script = ROOT / "scripts" / "semi_macro_browser.py"
    book_id = book_id or (read_csv(BOOKS_CSV)[0].get("book_id", "") if read_csv(BOOKS_CSV) else "")
    command = [
        sys.executable,
        str(script),
        "--platform",
        platform_id,
        "--book-id",
        book_id,
        "--books",
        str(BOOKS_CSV),
        "--platforms",
        str(PLATFORMS_CSV),
        "--profile",
        str(ROOT / "publisher_profile_template.csv"),
        "--mapping-dir",
        str(ROOT / "mappings"),
        "--browser-profile",
        str(ROOT / ".chromium_profile"),
        "--mode",
        "assist",
    ]
    return {"command": command, "powershell": " ".join(f'"{part}"' if " " in part else part for part in command)}


def save_book(payload: dict) -> dict:
    rows = read_csv(BOOKS_CSV)
    fieldnames = list(rows[0].keys()) if rows else list(payload.keys())
    if "book_id" not in payload or not payload["book_id"]:
        raise ValueError("book_id is required")
    for key in payload:
        if key not in fieldnames:
            fieldnames.append(key)
    replaced = False
    for index, row in enumerate(rows):
        if row.get("book_id") == payload["book_id"]:
            row.update({k: str(v) for k, v in payload.items()})
            rows[index] = row
            replaced = True
            break
    if not replaced:
        rows.append({k: str(v) for k, v in payload.items()})
    write_csv(BOOKS_CSV, rows, fieldnames)
    return {"ok": True, "replaced": replaced, "book_id": payload["book_id"]}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data: dict, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            return self.send_file(UI_PATH, "text/html; charset=utf-8")
        if parsed.path == "/api/state":
            return self.send_json(app_state())
        if parsed.path == "/api/assist-command":
            params = parse_qs(parsed.query)
            return self.send_json(
                assist_command(
                    book_id=(params.get("book_id") or [""])[0],
                    platform_id=(params.get("platform_id") or ["amazon_kdp"])[0],
                )
            )
        if parsed.path.startswith("/out/"):
            path = (ROOT / parsed.path.lstrip("/")).resolve()
            if ROOT in path.parents and path.exists():
                return self.send_file(path, "text/plain; charset=utf-8")
        self.send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/generate-packs":
                return self.send_json(generate_packs())
            if parsed.path == "/api/check-toolchain":
                return self.send_json(check_toolchain())
            if parsed.path == "/api/books":
                return self.send_json(save_book(self.read_payload()))
            if parsed.path == "/api/status":
                payload = self.read_payload()
                payload.setdefault("updated_at", datetime.now().isoformat(timespec="seconds"))
                rows = read_csv(STATUS_CSV)
                fieldnames = list(rows[0].keys()) if rows else list(payload.keys())
                for key in payload:
                    if key not in fieldnames:
                        fieldnames.append(key)
                updated = False
                for row in rows:
                    if row.get("book_id") == payload.get("book_id") and row.get("platform_id") == payload.get("platform_id"):
                        row.update({k: str(v) for k, v in payload.items()})
                        updated = True
                if not updated:
                    rows.append({k: str(v) for k, v in payload.items()})
                write_csv(STATUS_CSV, rows, fieldnames)
                return self.send_json({"ok": True, "updated": updated})
            self.send_json({"error": "not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def log_message(self, fmt: str, *args) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


def main() -> None:
    port = 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"전자책출판 독립프로그램 실행 중: http://127.0.0.1:{port}")
    print("종료하려면 Ctrl+C")
    server.serve_forever()


if __name__ == "__main__":
    main()
