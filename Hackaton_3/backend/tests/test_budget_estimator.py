from backend.models.schemas import BudgetConstraint
from backend.services.budget_estimator import BudgetEstimator


def test_budget_estimator_channel_shares_are_not_flat() -> None:
    estimator = BudgetEstimator()
    constraint = BudgetConstraint(low=100, high=900, currency="TND")

    whatsapp = estimator.estimate(
        "whatsapp",
        constraint,
        objective="sales",
        timeline="2 weeks",
        priority_rank=4,
        total_channels=6,
    )
    events = estimator.estimate(
        "events",
        constraint,
        objective="sales",
        timeline="2 weeks",
        priority_rank=0,
        total_channels=6,
    )

    assert float(whatsapp["total_high"]) <= 200
    assert float(events["total_high"]) >= 500
    assert float(whatsapp["total_high"]) < float(events["total_high"])


def test_budget_estimator_scales_with_timeline_and_objective() -> None:
    estimator = BudgetEstimator()
    constraint = BudgetConstraint(low=120, high=1200, currency="TND")

    base = estimator.estimate(
        "social_media",
        constraint,
        objective="awareness",
        timeline="1 week",
        priority_rank=2,
        total_channels=6,
    )
    scaled = estimator.estimate(
        "social_media",
        constraint,
        objective="sales",
        timeline="4 weeks",
        priority_rank=0,
        total_channels=6,
    )

    assert float(scaled["total_low"]) > float(base["total_low"])
    assert float(scaled["total_high"]) > float(base["total_high"])

    for key in ("content_creation", "ad_spend", "management", "tools"):
        assert key in scaled["breakdown"]
        assert float(scaled["breakdown"][key]) >= 0
