"""Versioned prompt templates.

Each prompt is its own file with frontmatter: prompt_id, version, model,
input/output schema. Edits bump the version. The eval harness runs every
versioned prompt against its fixture corpus before merge.
"""
