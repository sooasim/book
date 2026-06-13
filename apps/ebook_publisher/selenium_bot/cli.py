"""Selenium 반자동 게시 봇 — 명령줄 도구.

명령:
  list      [--region kr] [--automation api]        전 세계 플랫폼 레지스트리 출력
  validate                                            레지스트리 무결성 검증
  plan      --platform ID --book-json F [--epub F] [--cover F]   게시 계획(JSON, 브라우저 없음)
  signup-plan --platform ID [--email .. --name .. --pen .. --country ..]   가입 계획(JSON)
  collect   [--region kr] [--out report.json]         사이트 도달성/폼 프로빙(selenium 필요)
  assist    --platform ID --book-json F [--epub F] [--cover F] [--profile-dir D]
            실제 브라우저로 폼 자동 채움 + 업로드, 사람 게이트에서 정지(selenium 필요)

안전: assist/signup 은 회원가입 최종·CAPTCHA·본인인증·약관·독점·세금/정산·최종 게시를
      절대 자동 실행하지 않고 사람에게 넘긴다.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import registry as reg
from . import account_prep, batch, collector, profile_store
from .assistant import SeleniumAssistant, interactive_confirm
from .field_mapping import MappingStore
from .models import SignupProfile
from .publish_plan import build_publish_plan, plan_to_dict, plan_to_json


def _load_book(args) -> dict:
    if args.book_json:
        return json.loads(open(args.book_json, encoding="utf-8").read())
    book = {"book_id": args.book_id or "book_001", "title": args.title or "",
            "author": args.author or "", "description": args.description or "",
            "price_usd": args.price_usd or "", "language": args.language or "ko"}
    return book


def _files(args) -> dict:
    f = {}
    if args.epub:
        f["epub"] = args.epub
    if args.cover:
        f["cover"] = args.cover
    return f


def cmd_list(args) -> int:
    sites = reg.load_registry()
    sites = reg.filter_sites(sites, region=args.region, automation_level=args.automation)
    for s in sites:
        gates = ";".join(s.human_gates)
        print(f"{s.platform_id:22} {s.region:7} {s.automation_level:16} {s.platform_name}")
        if args.verbose:
            print(f"    url={s.primary_url}  signup={s.signup_url}")
            print(f"    human_gates={gates}")
    print(f"\n총 {len(sites)}개 (전체 {len(reg.load_registry())}개)")
    return 0


def cmd_validate(args) -> int:
    sites = reg.load_registry()
    rep = reg.validate_registry(sites)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(f"지역: {reg.regions(sites)}")
    print(f"자동화수준: {reg.automation_levels(sites)}")
    return 0 if rep["ok"] else 1


def cmd_plan(args) -> int:
    site = reg.get_site(reg.load_registry(), args.platform)
    if site is None:
        print(f"알 수 없는 platform: {args.platform}", file=sys.stderr)
        return 2
    plan = build_publish_plan(_load_book(args), site, _files(args))
    print(plan_to_json(plan))
    auto = sum(1 for s in plan.steps if s.action != "human_gate" and not s.human)
    print(f"\n자동 단계 {auto}개 · 사람 확인 게이트 {plan.human_gate_count()}개", file=sys.stderr)
    return 0


def cmd_signup_plan(args) -> int:
    site = reg.get_site(reg.load_registry(), args.platform)
    if site is None:
        print(f"알 수 없는 platform: {args.platform}", file=sys.stderr)
        return 2
    profile = SignupProfile(platform_id=site.platform_id, display_name=args.name or "",
                            email=args.email or "", pen_name=args.pen or "",
                            country=args.country or "")
    plan = account_prep.build_signup_plan(profile, site)
    print(json.dumps(plan_to_dict(plan), ensure_ascii=False, indent=2))
    return 0


def cmd_collect(args) -> int:
    sites = reg.load_registry()
    sites = reg.filter_sites(sites, region=args.region)
    from .driver import make_chrome, selenium_available
    if not selenium_available():
        print("selenium 미설치 — 오프라인 계획만 출력합니다.", file=sys.stderr)
        results = collector.probe_plan(sites)
    else:
        driver = make_chrome(profile_dir=args.profile_dir, headless=True)
        try:
            results = collector.probe_sites(sites, driver=driver)
        finally:
            driver.quit()
    out = args.out or "platform_probe_report.json"
    collector.write_report(results, out)
    print(json.dumps(collector.summarize_probe(results), ensure_ascii=False, indent=2))
    print(f"리포트: {out}")
    return 0


def cmd_assist(args) -> int:
    site = reg.get_site(reg.load_registry(), args.platform)
    if site is None:
        print(f"알 수 없는 platform: {args.platform}", file=sys.stderr)
        return 2
    # 기본정보가 저장되어 있으면 병합(한 번 입력 → 자동 사용)
    book = _load_book(args)
    saved = profile_store.load_book_profile(getattr(args, "base", None))
    if saved:
        book = {**saved, **{k: v for k, v in book.items() if v}}
    plan = build_publish_plan(book, site, _files(args))
    from .driver import make_chrome
    # 플랫폼별 영속 프로필 → 한 번 로그인하면 세션 유지(다음부터 로그인 생략)
    profile_dir = args.profile_dir or profile_store.profile_dir_for(
        site.platform_id, getattr(args, "base", None))
    driver = make_chrome(profile_dir=profile_dir, headless=False)
    assistant = SeleniumAssistant(driver=driver, mapping_store=MappingStore(),
                                  confirm=interactive_confirm)
    relog = "이미 로그인 세션 있음(로그인 생략 가능)" if profile_store.is_logged_in(
        site.platform_id, getattr(args, "base", None)) else "최초 로그인 필요(이후 유지)"
    print(f"브라우저가 열립니다. {relog}. 약관/최종 게시는 직접 하세요.\n")
    try:
        results = assistant.execute(plan)
    finally:
        pass  # 브라우저는 검수 위해 닫지 않음(사용자가 직접 종료)
    print(json.dumps(SeleniumAssistant.report(results), ensure_ascii=False, indent=2))
    return 0


def cmd_profile(args) -> int:
    if args.set_book:
        data = json.loads(open(args.set_book, encoding="utf-8").read())
        path = profile_store.save_book_profile(data, args.base)
        print(f"기본 책 정보 저장: {path}")
    if args.set_publisher:
        data = json.loads(open(args.set_publisher, encoding="utf-8").read())
        path = profile_store.save_publisher_profile(data, args.base)
        print(f"발행자 정보 저장: {path}")
    print("== 기본 책 정보 ==")
    print(json.dumps(profile_store.load_book_profile(args.base), ensure_ascii=False, indent=2))
    print("== 발행자 정보 ==")
    print(json.dumps(profile_store.load_publisher_profile(args.base), ensure_ascii=False, indent=2))
    return 0


def cmd_plan_all(args) -> int:
    """저장된 기본정보 1건으로 모든(필터된) 플랫폼 게시 계획을 일괄 생성."""
    book = profile_store.load_book_profile(args.base)
    if not book:
        print("기본 책 정보가 없습니다. 먼저 'profile --set-book book.json' 실행.", file=sys.stderr)
        return 2
    sites = reg.filter_sites(reg.load_registry(), region=args.region,
                             automation_level=args.automation)
    files = {}
    if args.epub:
        files["epub"] = args.epub
    if args.cover:
        files["cover"] = args.cover
    plans = batch.prepare_all(book, sites, files)
    out = args.out or "out_plans"
    manifest = batch.write_manifest(plans, out)
    print(json.dumps(batch.summary(plans), ensure_ascii=False, indent=2))
    print(f"매니페스트: {manifest}  (플랫폼별 계획 {len(plans)}개)")
    return 0


def cmd_inspect(args) -> int:
    """게시 페이지 구조를 자동 파악해 입력칸 매핑을 학습(selenium 필요)."""
    from . import inspector
    from .driver import make_chrome
    profile_dir = profile_store.profile_dir_for(args.platform, args.base)
    driver = make_chrome(profile_dir=profile_dir, headless=False)
    site = reg.get_site(reg.load_registry(), args.platform)
    if args.url:
        driver.get(args.url)
    elif site:
        driver.get(site.primary_url)
    input("로그인 후 '게시/책 등록' 폼 페이지를 연 뒤 Enter 를 누르세요... ")
    rep = inspector.learn_mapping(args.platform, driver, MappingStore())
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(f"세션 보존 위치(자동 로그인 유지): {profile_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="selenium_bot", description="반자동 전자책 게시 봇")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list"); pl.add_argument("--region"); pl.add_argument("--automation")
    pl.add_argument("--verbose", action="store_true"); pl.set_defaults(func=cmd_list)

    pv = sub.add_parser("validate"); pv.set_defaults(func=cmd_validate)

    def add_book_args(sp):
        sp.add_argument("--platform", required=True)
        sp.add_argument("--book-json"); sp.add_argument("--book-id")
        sp.add_argument("--title"); sp.add_argument("--author"); sp.add_argument("--description")
        sp.add_argument("--price-usd", dest="price_usd"); sp.add_argument("--language")
        sp.add_argument("--epub"); sp.add_argument("--cover")

    pp = sub.add_parser("plan"); add_book_args(pp); pp.set_defaults(func=cmd_plan)

    ps = sub.add_parser("signup-plan"); ps.add_argument("--platform", required=True)
    ps.add_argument("--email"); ps.add_argument("--name"); ps.add_argument("--pen")
    ps.add_argument("--country"); ps.set_defaults(func=cmd_signup_plan)

    pc = sub.add_parser("collect"); pc.add_argument("--region"); pc.add_argument("--out")
    pc.add_argument("--profile-dir"); pc.set_defaults(func=cmd_collect)

    pa = sub.add_parser("assist"); add_book_args(pa); pa.add_argument("--profile-dir")
    pa.add_argument("--base"); pa.set_defaults(func=cmd_assist)

    pr = sub.add_parser("profile")
    pr.add_argument("--set-book", dest="set_book"); pr.add_argument("--set-publisher", dest="set_publisher")
    pr.add_argument("--base"); pr.set_defaults(func=cmd_profile)

    pall = sub.add_parser("plan-all")
    pall.add_argument("--region"); pall.add_argument("--automation"); pall.add_argument("--base")
    pall.add_argument("--epub"); pall.add_argument("--cover"); pall.add_argument("--out")
    pall.set_defaults(func=cmd_plan_all)

    pi = sub.add_parser("inspect"); pi.add_argument("--platform", required=True)
    pi.add_argument("--url"); pi.add_argument("--base"); pi.set_defaults(func=cmd_inspect)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
