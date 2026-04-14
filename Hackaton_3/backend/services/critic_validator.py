from ..models.marketing import CriticResult
from ..models.schemas import SolutionItem


class CriticValidator:
    def validate(self, solutions: list[SolutionItem]) -> CriticResult:
        issues: list[str] = []

        if not solutions:
            return CriticResult(passed=False, issues=["No solutions generated"], score=0.0)

        names = [s.solution_name.strip().lower() for s in solutions]
        if len(names) != len(set(names)):
            issues.append("Duplicate solution names detected")

        channels = {s.channel for s in solutions}
        if len(channels) < 3:
            issues.append("Portfolio channel diversity too low (<3 channels)")

        has_low_budget = any(s.budget.total_high <= 150 for s in solutions)
        has_scale_option = any(s.budget.total_high >= 500 for s in solutions)

        if not has_low_budget:
            issues.append("Missing quick-win low budget option")
        if not has_scale_option:
            issues.append("Missing scale play option (>=500 TND)")

        score = max(0.0, 1.0 - (0.2 * len(issues)))
        return CriticResult(passed=len(issues) == 0, issues=issues, score=score)
