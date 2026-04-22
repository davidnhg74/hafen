"""AI-powered services.

`client.py` is the low-level Anthropic wrapper (caching, retries, telemetry,
token-budget tracking). `prompts/` holds versioned prompt templates with their
eval fixtures. `services/` are high-level features that combine prompts +
deterministic logic (code translator, app-impact analyzer, runbook generator,
schema modernization advisor).

Every AI call carries a prompt_version + model_id in its trace so we can
attribute regressions to specific prompt or model changes.
"""
