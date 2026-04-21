import math
from dataclasses import dataclass
from typing import Dict, List
from ..parsers.plsql_parser import PlSqlParser, ConstructType


@dataclass
class ComplexityReport:
    score: int  # 1-100
    total_lines: int
    auto_convertible_lines: int
    needs_review_lines: int
    must_rewrite_lines: int
    construct_counts: Dict[str, int]
    tier_b_constructs: List[str]
    tier_c_constructs: List[str]
    effort_estimate_days: float
    estimated_cost: float
    top_10_constructs: List[str]


class ComplexityScorer:
    def __init__(self):
        self.parser = PlSqlParser()

    def analyze(self, content: str, rate_per_day: int = 1000) -> ComplexityReport:
        """Analyze PL/SQL complexity and return detailed report."""
        # Parse content
        parse_result = self.parser.parse(content)

        # Count constructs by type
        construct_counts = self._count_constructs(parse_result.constructs)

        # Get tier lists
        tier_b_list = [c.name for c in parse_result.constructs if c.type in self.parser.tier_b_constructs]
        tier_c_list = [c.name for c in parse_result.constructs if c.type in self.parser.tier_c_constructs]

        # Get top 10 hardest constructs
        tier_c_names = [c.name for c in parse_result.constructs if c.type in self.parser.tier_c_constructs]
        tier_b_names = [c.name for c in parse_result.constructs if c.type in self.parser.tier_b_constructs]
        top_10 = tier_c_names + tier_b_names[:10-len(tier_c_names)]

        # Calculate complexity score
        score = self._calculate_score(
            parse_result.total_lines,
            parse_result.tier_a_lines,
            parse_result.tier_b_lines,
            parse_result.tier_c_lines,
            construct_counts
        )

        # Estimate effort
        effort_days = self._estimate_effort(
            parse_result.tier_a_lines,
            parse_result.tier_b_lines,
            parse_result.tier_c_lines
        )

        estimated_cost = effort_days * rate_per_day

        return ComplexityReport(
            score=score,
            total_lines=parse_result.total_lines,
            auto_convertible_lines=parse_result.tier_a_lines,
            needs_review_lines=parse_result.tier_b_lines,
            must_rewrite_lines=parse_result.tier_c_lines,
            construct_counts=construct_counts,
            tier_b_constructs=tier_b_list,
            tier_c_constructs=tier_c_list,
            effort_estimate_days=effort_days,
            estimated_cost=estimated_cost,
            top_10_constructs=top_10,
        )

    def _count_constructs(self, constructs) -> Dict[str, int]:
        """Count constructs by type."""
        counts = {}
        for construct in constructs:
            type_name = construct.type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts

    def _calculate_score(
        self, total_lines: int, tier_a: int, tier_b: int, tier_c: int, construct_counts: Dict[str, int]
    ) -> int:
        """
        Calculate complexity score 1-100.

        Formula:
        - Tier A (weight 1): auto-convertible
        - Tier B (weight 5): needs-review
        - Tier C (weight 20): must-rewrite

        raw = (tier_b * 5 + tier_c * 20) / max(total_lines, 1)
        score = min(100, int(raw * 10 + log10(total_lines) * 5))
        """
        total_constructs = sum(construct_counts.values()) or 1

        # Weighted score for constructs
        construct_weight = (tier_b * 5 + tier_c * 20) / max(total_constructs, 1)

        # Line-based score
        line_weight = min(10, total_lines / 1000) if total_lines > 0 else 0

        # Logarithmic scale for file size
        size_factor = math.log10(max(total_lines, 1)) * 5 if total_lines > 0 else 0

        raw_score = construct_weight * 10 + line_weight + size_factor
        score = min(100, int(raw_score))

        return max(1, score)

    def _estimate_effort(self, tier_a: int, tier_b: int, tier_c: int) -> float:
        """
        Estimate effort in engineer-days.

        Tier A (auto-convertible): 0.1 engineer-days per 1000 lines
        Tier B (needs-review): 0.5 engineer-days per 100 lines
        Tier C (must-rewrite): 2.0 engineer-days per 100 lines
        """
        a_days = (tier_a / 1000) * 0.1 if tier_a > 0 else 0
        b_days = (tier_b / 100) * 0.5 if tier_b > 0 else 0
        c_days = (tier_c / 100) * 2.0 if tier_c > 0 else 0

        total_days = a_days + b_days + c_days
        return max(0.5, round(total_days, 1))  # Minimum 0.5 days
