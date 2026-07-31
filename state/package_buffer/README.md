# Reserve package bank

Cover for a dead brain — no Routine run, a revoked `CLAUDE_CODE_OAUTH_TOKEN`,
a lapsed subscription. Full explanation: `docs/FALLBACKS.md` §5.

    inbox/      the Routine drops EVERGREEN extras here; CI banks them
    packages/   the bank itself, one JSON per package
    used.json   append-only ledger of what has been drawn (never re-serve)

    python scripts/package_reserve.py status
    python scripts/package_reserve.py deposit --dir state/package_buffer/inbox --dry-run
    python scripts/package_reserve.py fill --date 20260801 --dry-run

Small JSON only — the same storage rule as the rest of `state/`.
