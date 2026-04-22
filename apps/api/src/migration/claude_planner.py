"""
Claude-powered migration strategy planning.
Analyzes schema and generates optimized migration plans.
"""

import json
import logging
from anthropic import Anthropic
from typing import Dict, List

logger = logging.getLogger(__name__)


class MigrationPlanner:
    """Uses Claude to optimize migration strategy."""

    def __init__(self, api_key: str = None):
        from ..config import settings

        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = "claude-opus-4-7"

    def analyze_schema(
        self,
        tables: List[Dict],
        available_memory_gb: int = 8,
        available_bandwidth_mbps: int = 100,
    ) -> Dict:
        """
        Analyze schema and generate migration strategy.

        Args:
            tables: [{"name": "CUSTOMERS", "rows": 5M, "size_gb": 2, "has_fk": False}, ...]
            available_memory_gb: System memory for chunking
            available_bandwidth_mbps: Network throughput

        Returns:
            Migration strategy with chunk sizes, parallelization, order, recommendations
        """

        # Build schema description
        schema_description = self._format_schema(tables)

        prompt = f"""You are an expert Oracle-to-PostgreSQL migration architect.

Analyze this Oracle schema and generate an optimized migration strategy.

SCHEMA:
{schema_description}

CONSTRAINTS:
- Available memory: {available_memory_gb} GB
- Network throughput: {available_bandwidth_mbps} Mbps
- Minimize downtime (target: <1 hour for cutover)
- Ensure data consistency (exact row counts, no loss)

For each table, determine:
1. Optimal chunk size (balance: memory vs throughput vs lock contention)
2. Parallelization strategy (which tables can run simultaneously)
3. Migration order (respect foreign key dependencies)
4. Estimated duration

IMPORTANT: Output ONLY valid JSON with no markdown. No code blocks, no explanations.

Output format:
{{
  "table_order": ["TABLE1", "TABLE2", ...],
  "chunk_size": {{"TABLE1": 10000, "TABLE2": 50000, ...}},
  "num_workers": 4,
  "parallel_groups": [["TABLE1", "TABLE2"], ["TABLE3"]],
  "estimated_duration_minutes": 45,
  "throughput_mbs": 120,
  "risks": [
    "TABLE1: Large CLOB column may cause memory spike",
    "TABLE2_TO_TABLE3 FK: Ensure CUSTOMERS migrates first"
  ],
  "optimizations": [
    "Add index on ORDERS.customer_id before migration (5% speedup)",
    "Disable triggers during migration, re-enable after (10% speedup)"
  ]
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            strategy = json.loads(response_text)

            logger.info(
                f"Migration strategy generated: "
                f"{len(strategy.get('table_order', []))} tables, "
                f"{strategy.get('estimated_duration_minutes')} min estimated"
            )

            return strategy

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            return self._default_strategy(tables)
        except Exception as e:
            logger.error(f"Claude planning error: {e}")
            return self._default_strategy(tables)

    def analyze_errors(self, error_log: List[str]) -> Dict:
        """
        Analyze migration errors and suggest remediation.

        Args:
            error_log: List of error messages from migration

        Returns:
            Remediation suggestions
        """

        if not error_log:
            return {"status": "no_errors"}

        prompt = f"""You are an expert at diagnosing Oracle-to-PostgreSQL migration errors.

Analyze these migration errors and suggest fixes:

ERROR LOG:
{json.dumps(error_log, indent=2)}

For each error, suggest:
1. Root cause analysis
2. Immediate fix (if safe)
3. Long-term prevention

Output ONLY valid JSON:
{{
  "errors_analyzed": [
    {{
      "error": "...",
      "cause": "...",
      "immediate_fix": "...",
      "prevention": "..."
    }}
  ],
  "overall_action": "CONTINUE|RETRY|ABORT"
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text.strip()

            # Clean markdown
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            analysis = json.loads(response_text)

            logger.info(
                f"Error analysis: {len(analysis.get('errors_analyzed', []))} issues identified"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analysis failed: {e}")
            return {"status": "analysis_failed", "error": str(e)}

    @staticmethod
    def _format_schema(tables: List[Dict]) -> str:
        """Format schema for Claude prompt."""
        lines = []

        for table in tables:
            lines.append(
                f"- {table['name']}: "
                f"{table.get('rows', 'unknown')} rows, "
                f"{table.get('size_gb', '?')} GB, "
                f"{'FK: Yes' if table.get('has_fk') else 'No FK'}"
            )

        return "\n".join(lines)

    @staticmethod
    def _default_strategy(tables: List[Dict]) -> Dict:
        """Generate fallback strategy if Claude fails."""
        table_names = [t["name"] for t in tables]

        # Sort by size (smallest first for dependencies)
        sorted_tables = sorted(tables, key=lambda x: x.get("size_gb", 0))

        chunk_sizes = {}
        for table in sorted_tables:
            rows = table.get("rows", 1000000)

            if rows < 10000:
                chunk_sizes[table["name"]] = rows
            elif rows < 1_000_000:
                chunk_sizes[table["name"]] = 10000
            elif rows < 10_000_000:
                chunk_sizes[table["name"]] = 100000
            else:
                chunk_sizes[table["name"]] = 1_000_000

        total_gb = sum(t.get("size_gb", 0) for t in tables)
        estimated_minutes = max(45, int(total_gb * 15))  # ~1 min per GB + buffer

        return {
            "table_order": [t["name"] for t in sorted_tables],
            "chunk_size": chunk_sizes,
            "num_workers": 4,
            "parallel_groups": [[t["name"]] for t in sorted_tables],
            "estimated_duration_minutes": estimated_minutes,
            "throughput_mbs": 100,
            "risks": [
                "Default strategy used (Claude unavailable)",
                "Consider manual review for optimal performance",
            ],
            "optimizations": ["Enable compression on large tables"],
        }
