"""일괄 오케스트레이션 — 기본정보 하나로 모든 플랫폼 게시/가입 계획을 생성.

"기본정보가 한번 입력되면 모든 곳에 자동 입력" 요구의 구현:
  - prepare_all(book, sites): 저장된 단일 book 메타데이터로 전 플랫폼 게시 계획 생성.
  - signup_all(publisher, sites): 단일 발행자 정보로 전 플랫폼 가입(보조) 계획 생성.
실제 브라우저 실행은 assistant 가, 사람 게이트(약관/최종 게시 등)는 사람이 담당.
"""
from __future__ import annotations

import json
from pathlib import Path

from .account_prep import build_signup_plan
from .models import PlatformSite, SignupProfile
from .publish_plan import build_publish_plan, plan_to_dict


def prepare_all(book: dict, sites: list[PlatformSite],
                files: dict | None = None) -> dict[str, object]:
    """전 플랫폼 게시 계획. {platform_id: PublishPlan}."""
    return {s.platform_id: build_publish_plan(book, s, files) for s in sites}


def signup_all(publisher: dict, sites: list[PlatformSite]) -> dict[str, object]:
    """전 플랫폼 가입 보조 계획. {platform_id: PublishPlan}."""
    plans = {}
    for s in sites:
        profile = SignupProfile(
            platform_id=s.platform_id,
            display_name=publisher.get("display_name", ""),
            email=publisher.get("email", ""),
            pen_name=publisher.get("pen_name", ""),
            country=publisher.get("country", ""),
        )
        plans[s.platform_id] = build_signup_plan(profile, s)
    return plans


def summary(plans: dict[str, object]) -> dict:
    """플랫폼별 자동 단계/사람 게이트 수 요약."""
    out = {}
    for pid, plan in plans.items():
        auto = sum(1 for s in plan.steps if s.action not in ("human_gate", "wait_human_login"))
        out[pid] = {"steps": len(plan.steps), "auto": auto,
                    "human_gates": plan.human_gate_count()}
    return {"platforms": len(plans), "by_platform": out}


def write_manifest(plans: dict[str, object], out_dir: str) -> str:
    """플랫폼별 계획 JSON + manifest 저장."""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    manifest = {"platforms": [], "total": len(plans)}
    for pid, plan in plans.items():
        path = d / f"{pid}.plan.json"
        path.write_text(json.dumps(plan_to_dict(plan), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        manifest["platforms"].append({"platform_id": pid, "file": str(path),
                                      "human_gates": plan.human_gate_count()})
    mpath = d / "manifest.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(mpath)
