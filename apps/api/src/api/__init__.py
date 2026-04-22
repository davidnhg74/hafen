"""HTTP surface (FastAPI app + routes).

The current monolithic `src/main.py` is being decomposed module by module into
`api/routes/<feature>.py` as features get rebuilt on the new architecture.
The app factory lives at `api/app.py` once the move begins.
"""
