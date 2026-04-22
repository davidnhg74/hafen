"""Diagnostics: errors, warnings, and remediation suggestions.

Every transformation, AI rewrite, and validator produces Diagnostics rather than
raising. A Diagnostic has severity, location (source span), code, message, and
optional fix suggestion. The UI groups them; the runbook generator turns them
into ordered work items for the customer.
"""
