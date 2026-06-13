"""반자동 게시 어시스턴트 — 계획(PublishPlan)을 실행한다.

핵심 안전 규칙:
  - 자동화 가능한 단계(open_url/fill/upload/select/click_safe/verify_review)만 브라우저로 실행.
  - human_gate 단계는 **절대 자동 실행하지 않는다**. 사람에게 안내하고 확인(confirm)을 기다린다.
  - wait_human_login 도 사람이 직접 로그인하도록 정지한다.
  - driver=None 이면 드라이 런(브라우저 없이 계획만 점검) — selenium 미설치 환경에서 동작.

confirm(step)->bool 콜백:
  - human_gate/login 에서 호출. True 면 "사람이 처리 완료"로 보고 다음 단계로,
    False 면 거기서 정지(halted_for_human). 비대화형 기본값은 정지(False).
"""
from __future__ import annotations

from . import gates
from .field_mapping import MappingStore
from .models import FieldSelector, PlanStep, PublishPlan, StepResult


def _noninteractive_confirm(step: PlanStep) -> bool:
    """기본 confirm: 사람 개입 지점에서 정지(자동 진행하지 않음)."""
    return False


def interactive_confirm(step: PlanStep) -> bool:  # pragma: no cover - 대화형 전용
    label = gates.gate_label(step.gate) if step.gate else step.note
    print(f"\n[사람 확인 필요] {label}")
    print(f"  → 브라우저에서 직접 처리한 뒤 Enter (건너뛰려면 's'+Enter): ", end="")
    try:
        ans = input().strip().lower()
    except EOFError:
        return False
    return ans != "s"


class SeleniumAssistant:
    def __init__(self, driver=None, mapping_store: MappingStore | None = None, confirm=None):
        self.driver = driver
        self.store = mapping_store or MappingStore()
        self.confirm = confirm or _noninteractive_confirm

    # ---------------------------------------------------------------- 셀렉터 해석
    def _resolve_selector(self, platform_id: str, step: PlanStep) -> FieldSelector | None:
        if step.selector:
            return FieldSelector(step.field_key or "", step.by or "css", step.selector)
        return self.store.resolve(platform_id, step.field_key)

    # ---------------------------------------------------------------- 실행
    def execute(self, plan: PublishPlan) -> list[StepResult]:
        results: list[StepResult] = []
        for step in plan.steps:
            # 안전 가드: 알 수 없는 액션은 차단.
            gates.guard_action(step.action)

            if step.action == "human_gate":
                # 사람 게이트는 브라우저로 절대 자동 실행하지 않는다(아래에서 _do_auto 미호출).
                ok = self.confirm(step)
                results.append(StepResult(step, "done" if ok else "halted_for_human",
                                          gates.gate_label(step.gate)))
                if not ok:
                    break
                continue

            if step.action == "wait_human_login":
                ok = self.confirm(step)
                results.append(StepResult(step, "done" if ok else "halted_for_human",
                                          "사람이 직접 로그인"))
                if not ok:
                    break
                continue

            # 자동화 단계
            if self.driver is None:
                results.append(StepResult(step, "skipped", "dry-run (드라이버 없음)"))
                continue
            try:
                self._do_auto(plan.platform_id, step)
                results.append(StepResult(step, "done"))
            except Exception as exc:  # noqa: BLE001
                results.append(StepResult(step, "error", str(exc)))
                break
        return results

    def _do_auto(self, platform_id: str, step: PlanStep) -> None:
        if step.action == "open_url":
            self.driver.get(step.value)
            return
        if step.action in ("verify_review", "screenshot"):
            return
        sel = self._resolve_selector(platform_id, step)
        if sel is None:
            raise RuntimeError(
                f"입력칸 매핑 없음: '{step.field_key}'. "
                f"mappings/{platform_id}.json 에 셀렉터를 추가하세요(field_mapping.set_field)."
            )
        from .driver import by_method
        element = self.driver.find_element(by_method(sel.by), sel.selector)
        if step.action == "fill":
            try:
                element.clear()
            except Exception:
                pass
            element.send_keys(step.value)
        elif step.action == "upload":
            element.send_keys(step.value)   # <input type=file> 에 경로 전송
        elif step.action == "select":
            element.send_keys(step.value)
        elif step.action == "click_safe":
            element.click()

    # ---------------------------------------------------------------- 리포트
    @staticmethod
    def report(results: list[StepResult]) -> dict:
        counts: dict[str, int] = {}
        for r in results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return {
            "total": len(results),
            "counts": counts,
            "halted": any(r.status == "halted_for_human" for r in results),
            "errors": [r.message for r in results if r.status == "error"],
            "steps": [
                {"action": r.step.action, "field": r.step.field_key, "gate": r.step.gate,
                 "status": r.status, "message": r.message}
                for r in results
            ],
        }
