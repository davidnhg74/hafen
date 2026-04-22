"""Tests for the legacy PDFReportGenerator (the /api/v1/analyze PDF)."""

import io

import pytest
from pypdf import PdfReader

from src.analyze.complexity import analyze
from src.reports.pdf_generator import PDFReportGenerator


@pytest.fixture
def sample_report():
    src = """
    CREATE OR REPLACE PROCEDURE upsert_employee AS
        PRAGMA AUTONOMOUS_TRANSACTION;
        v_id employees.employee_id%TYPE;
    BEGIN
        MERGE INTO employees t USING staging s ON (t.id = s.id)
        WHEN MATCHED THEN UPDATE SET t.name = s.name;
        SELECT id INTO v_id FROM employees
            START WITH manager_id IS NULL
            CONNECT BY PRIOR id = manager_id;
        DBMS_OUTPUT.PUT_LINE('hi');
    END;
    """
    return analyze(src, rate_per_day=1500)


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


class TestLegacyPdfGenerator:
    def test_returns_pdf_bytes(self, sample_report):
        out = PDFReportGenerator().generate(sample_report)
        assert isinstance(out, bytes)
        assert out.startswith(b"%PDF-")
        assert len(out) > 1000

    def test_includes_score_and_lines(self, sample_report):
        text = _pdf_text(PDFReportGenerator().generate(sample_report))
        assert "Complexity score" in text
        assert str(sample_report.score) in text
        # Tier rows render as "A — auto-convertible" etc. across table cells.
        assert "auto-convertible" in text
        assert "needs review" in text
        assert "must rewrite" in text

    def test_includes_effort_and_cost(self, sample_report):
        text = _pdf_text(PDFReportGenerator().generate(sample_report))
        assert "Effort estimate" in text
        assert str(sample_report.effort_estimate_days) in text

    def test_lists_tier_c_constructs(self, sample_report):
        # The fixture has AUTONOMOUS_TXN — Tier C.
        text = _pdf_text(PDFReportGenerator().generate(sample_report))
        assert "AUTONOMOUS_TXN" in text or "Tier-C" in text
