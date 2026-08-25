# RecoverAI Test Suites

This directory contains test suites across all project tiers:

- `backend/tests/`: FastAPI route tests, schema validators, policy engine tests, database model tests.
- `tests/`: End-to-end integration workflows (Detect -> Diagnose -> Decide -> Execute -> Verify -> Measure).

Run backend tests:
```powershell
cd backend
pytest -v
```
