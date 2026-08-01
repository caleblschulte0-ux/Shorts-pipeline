# Claude: Start Here

Read `docs/CLAUDE_MASTER_PLAYBOOK.md` before changing code.

Then read:

1. `docs/CLAUDE_HANDOFF_MANIFEST.json`
2. `docs/CURIOSITY_FINAL_REPORT.md`
3. `docs/CLAUDE_AUTONOMY_LAUNCHOFF.md`
4. `docs/CLAUDE_EXECUTION_CHECKLIST.md`
5. `experiments/curiosity_nextgen/README.md`

`docs/CLAUDE_MASTER_PLAYBOOK.md` is the canonical source of truth. It supersedes older named-video optimization and three-story proof instructions in `docs/CLAUDE_CONTINUATION_PLAYBOOK.md`.

Immediate action:

```bash
git fetch origin
gh pr checkout 173
git rev-parse HEAD
python -m compileall experiments/curiosity_nextgen
python -m unittest discover -v experiments/curiosity_nextgen/tests
```

Fix every failure without weakening contracts or touching production paths. Report exact commands, exit codes, counts, duration, commits, files changed, and final head SHA.

Publishing must remain disabled. Do not add another dormant subsystem. Do not import PR #173 wholesale. Do not use story identity to select behavior.