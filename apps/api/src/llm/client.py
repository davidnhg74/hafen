from anthropic import Anthropic
from ..config import settings


class LLMClient:
    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    def convert_plsql(self, plsql_code: str, context: str = "") -> str:
        """
        Convert PL/SQL to PL/pgSQL using Claude.
        Phase 2 implementation.
        """
        prompt = f"""You are an expert Oracle DBA and PostgreSQL engineer.
Convert the following Oracle PL/SQL code to PostgreSQL PL/pgSQL.
Output ONLY the converted code, no explanations.

Oracle PL/SQL:
{plsql_code}

Context: {context}
"""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text

    def analyze_complexity(self, plsql_code: str) -> dict:
        """
        Analyze PL/SQL complexity using Claude.
        Phase 2 optimization - currently handled deterministically.
        """
        # Stub for Phase 2
        return {}
