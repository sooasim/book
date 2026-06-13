"""Selenium 반자동 게시 봇 — 공유 데이터 모델 및 안전 게이트 계약 (동결).

설계 원칙(이 저장소의 일관된 안전 경계, docs/00~14 및 semi_macro_browser 와 동일):
  - 자동화는 "반복 입력 · 폼 자동 채움 · 파일 업로드"까지만 한다.
  - 회원가입 최종 완료 · CAPTCHA · 본인인증 · 약관 동의 · 독점 계약 ·
    세금/정산 입력 · 최종 게시(Publish) 버튼은 **사람이 직접** 한다(HUMAN GATE).
  - 코드는 HUMAN GATE 를 절대 자동 통과하지 않는다(gates.assert_not_automatable).

이 파일은 동결 계약이다. 모든 모듈이 여기에 의존한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Region = Literal["global", "us", "eu", "de", "fr", "kr", "jp", "cn", "in", "africa", "other"]
EntryType = Literal[
    "self_publish", "aggregator", "aggregator_pod", "direct_store",
    "retailer_partner", "service", "community",
]
AutomationLevel = Literal[
    "api",                # 공식 API/대량 업로드(가장 안전, 가능 시 우선)
    "assisted_browser",   # 로그인 후 폼 자동 채움 보조(최종 제출은 사람)
    "aggregator",         # 배급사 경유(여러 스토어 일괄)
    "manual_contract",    # 입점 계약/서류 필요(자동화는 자료 준비까지)
    "direct_store",       # 직접 판매 스토어
]

# ---------------------------------------------------------------- 사람 확인 게이트
# 이 단계들은 법적 책임/플랫폼 약관/봇 차단 때문에 절대 자동화하지 않는다.
HUMAN_GATES: tuple[str, ...] = (
    "account_create_final",   # 회원가입 최종 완료
    "captcha",                # 캡차
    "email_verify",           # 이메일 인증
    "phone_verify",           # 휴대폰 본인인증
    "identity_verify",        # 신원/사업자 인증
    "tos_agree",              # 약관 동의
    "content_rights_confirm", # 저작권/출판권 확인
    "ai_disclosure",          # AI 생성/보조 콘텐츠 고지
    "exclusivity",            # 독점 계약(예: KDP Select)
    "tax_info",               # 세금 정보
    "payout_info",            # 정산 계좌
    "pricing_confirm",        # 최종 가격/통화 확정
    "final_submit",           # 최종 게시(Publish) 버튼
)

# 자동화가 허용되는 액션(폼 채움·업로드·비위험 클릭·검수).
AUTOMATABLE_ACTIONS: tuple[str, ...] = (
    "open_url", "wait_human_login", "fill", "select", "upload",
    "click_safe", "verify_review", "screenshot",
)

ByMethod = Literal["css", "xpath", "id", "name"]
FieldType = Literal["text", "textarea", "file", "select", "checkbox", "button"]


@dataclass
class PlatformSite:
    """전 세계 전자책 플랫폼 레지스트리 한 건."""
    platform_id: str
    region: str
    platform_name: str
    entry_type: str
    primary_url: str
    signup_url: str = ""
    api_available: bool = False
    automation_level: str = "assisted_browser"
    human_gates: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class FieldSelector:
    """플랫폼 입력칸 매핑 한 건(학습 저장 대상)."""
    field_key: str            # title/subtitle/description/keywords/price/manuscript/cover ...
    by: ByMethod
    selector: str
    field_type: FieldType = "text"


@dataclass
class PlanStep:
    """게시/가입 계획의 한 단계."""
    action: str               # AUTOMATABLE_ACTIONS 중 하나 또는 "human_gate"
    note: str = ""
    field_key: str = ""
    value: str = ""           # 민감값은 plan 에 저장하지 않음(빈 문자열/플레이스홀더)
    selector: str = ""
    by: str = ""
    gate: str = ""            # action=="human_gate" 일 때 HUMAN_GATES 중 하나
    human: bool = False       # True 면 사람이 직접 수행해야 함


@dataclass
class PublishPlan:
    platform_id: str
    book_id: str
    steps: list[PlanStep] = field(default_factory=list)
    created_at: str = ""

    def human_gate_count(self) -> int:
        return sum(1 for s in self.steps if s.action == "human_gate")


@dataclass
class StepResult:
    step: PlanStep
    status: Literal["done", "halted_for_human", "skipped", "error"]
    message: str = ""


@dataclass
class SignupProfile:
    """가입 폼 자동 채움용 프로필. 비밀번호/주민·사업자번호는 저장하지 않는다."""
    platform_id: str
    display_name: str = ""
    email: str = ""           # 가입 이메일(인증은 사람이)
    pen_name: str = ""
    country: str = ""
    # 비밀번호/세금/계좌/주민번호 등 민감정보 필드는 의도적으로 두지 않음.
