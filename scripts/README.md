# Scripts

Developer utilities for local setup and packaging.

## `seed.py`

Seeds the database with 3 demo songs and runs the full agent pipeline for each.

```bash
python -m scripts.seed
```

Run from the repository root. Requires the backend environment (see `.env.example`) to be configured.

## `package_demo.ps1`

Creates `dist/ai-music-marketer-demo.zip` containing the project source, excluding
`.git`, `.venv`, `node_modules`, `.next`, `__pycache__`, `.pytest_cache`,
`private-media`, `dist` and `coverage`.

```powershell
pwsh -File scripts/package_demo.ps1
```

Fails if the archive already exists — move it before packaging again.
