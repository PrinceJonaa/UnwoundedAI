from app.schemas import L3PromotionCandidate
from app.services.promotion import L3PromotionPolicy


def test_blocks_tool_output_candidates() -> None:
    policy = L3PromotionPolicy()
    candidate = L3PromotionCandidate(
        key="x",
        value="tool said this",
        memory_type="stable_rule",
        confidence=0.95,
        requires_user_confirmation=False,
        verification_count=10,
        source="tool_output",
    )
    assert policy.should_promote(candidate, user_confirmed=True) is False


def test_requires_explicit_confirmation_when_flagged() -> None:
    policy = L3PromotionPolicy()
    candidate = L3PromotionCandidate(
        key="pref",
        value="my preference",
        memory_type="preference",
        confidence=0.8,
        requires_user_confirmation=True,
        source="user_message",
    )
    assert policy.should_promote(candidate, user_confirmed=False) is False
    assert policy.should_promote(candidate, user_confirmed=True) is True
