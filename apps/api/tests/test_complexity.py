import pytest
from src.analyzers.complexity_scorer import ComplexityScorer
from src.parsers.plsql_parser import ConstructType


class TestComplexityScorer:
    @pytest.fixture
    def scorer(self):
        return ComplexityScorer()

    def test_simple_procedure(self, scorer, simple_procedure):
        """Test scoring of a simple procedure."""
        report = scorer.analyze(simple_procedure)

        assert report.score >= 1
        assert report.score <= 100
        assert report.total_lines > 0
        assert report.effort_estimate_days > 0
        assert len(report.construct_counts) > 0

    def test_hr_schema(self, scorer, hr_schema_content):
        """Test complexity analysis of HR schema."""
        report = scorer.analyze(hr_schema_content)

        # Should find multiple constructs
        assert len(report.construct_counts) > 3
        assert report.total_lines > 50

        # Should detect specific constructs
        assert any("PROCEDURE" in key for key in report.construct_counts.keys())
        assert any("FUNCTION" in key for key in report.construct_counts.keys())
        assert any("PACKAGE" in key for key in report.construct_counts.keys())

        # Should have some tier B constructs
        assert len(report.tier_b_constructs) > 0

        # Should have some tier C constructs
        assert len(report.tier_c_constructs) > 0

    def test_complex_plsql(self, scorer, complex_plsql):
        """Test scoring of complex PL/SQL."""
        report = scorer.analyze(complex_plsql)

        # Should detect tier B and C constructs
        assert report.score > 30  # Moderate to high complexity
        assert any("MERGE" in str(c) for c in report.top_10_constructs)
        assert any("CONNECT_BY" in str(c) for c in report.top_10_constructs)

    def test_effort_estimation(self, scorer, hr_schema_content):
        """Test effort estimation."""
        report = scorer.analyze(hr_schema_content, rate_per_day=1000)

        # Effort should be reasonable
        assert report.effort_estimate_days > 0
        assert report.effort_estimate_days < 100  # Sanity check

        # Cost should reflect effort
        expected_cost = report.effort_estimate_days * 1000
        assert report.estimated_cost == expected_cost

    def test_custom_rate(self, scorer, simple_procedure):
        """Test custom rate per day."""
        report1 = scorer.analyze(simple_procedure, rate_per_day=1000)
        report2 = scorer.analyze(simple_procedure, rate_per_day=2000)

        # Cost should double with 2x rate
        assert report2.estimated_cost == report1.estimated_cost * 2

    def test_empty_content(self, scorer):
        """Test handling of empty content."""
        report = scorer.analyze("")

        assert report.score >= 1
        assert report.total_lines == 0
        assert report.effort_estimate_days == 0.5  # Minimum

    def test_construct_counts(self, scorer, hr_schema_content):
        """Test construct counting."""
        report = scorer.analyze(hr_schema_content)

        # Verify construct counts are positive integers
        for count in report.construct_counts.values():
            assert isinstance(count, int)
            assert count > 0

    def test_line_classification(self, scorer, complex_plsql):
        """Test line classification into tiers."""
        report = scorer.analyze(complex_plsql)

        total_classified = (
            report.auto_convertible_lines
            + report.needs_review_lines
            + report.must_rewrite_lines
        )

        # Some lines should be classified
        assert total_classified > 0

    def test_top_10_constructs(self, scorer, hr_schema_content):
        """Test top 10 constructs identification."""
        report = scorer.analyze(hr_schema_content)

        # Should have top constructs
        assert len(report.top_10_constructs) > 0
        assert len(report.top_10_constructs) <= 10

    def test_score_range(self, scorer, hr_schema_content):
        """Test that score is always 1-100."""
        for _ in range(5):
            report = scorer.analyze(hr_schema_content)
            assert 1 <= report.score <= 100
