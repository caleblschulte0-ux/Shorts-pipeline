"""Local demonstration CLI for the isolated Professional Media OS prototype."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .contracts import PortfolioConstraints, to_primitive
from .counterfactual import (
    CounterfactualChange,
    CounterfactualRunner,
    TransparentHeuristicPredictor,
)
from .fixtures import candidate, evidence, genome
from .lab import CandidateTournament, EvaluationContext
from .ledger import FileLedger
from .portfolio import PortfolioPlanner, ScoredCandidate


def build_demo() -> Mapping[str, Any]:
    primary = evidence()
    context = EvaluationContext(
        evidence={primary.evidence_id: primary},
        allowed_rights_risks=("green",),
        allowed_formats_by_channel={"channel-daily": ("narrated-proof",)},
        recent_hook_structures_by_channel={
            "channel-daily": (
                "consequence-first",
                "consequence-first",
                "chronology",
                "consequence-first",
            )
        },
        recent_title_patterns_by_channel={
            "channel-daily": (
                "entity-plus-consequence",
                "question-gap",
                "entity-plus-consequence",
            )
        },
    )

    consequence = candidate()
    proof_first = candidate(
        "candidate-proof-first-001",
        genome_value=genome(
            "genome-proof-first-001",
            hook_structure="proof-first",
            title_pattern="proof-plus-question",
            first_subject_ms=0,
            first_proof_ms=0,
            novelty_score=0.92,
            estimated_cost=0.40,
            estimated_runtime_seconds=150.0,
        ),
        estimated_value=4.4,
        opening_line="This document is the part they hoped nobody would read.",
        payoff_line="The document showed the rule had been applied to the wrong person.",
    )
    suspense = candidate(
        "candidate-suspense-001",
        genome_value=genome(
            "genome-suspense-001",
            hook_structure="withheld-outcome",
            title_pattern="decision-plus-hidden-detail",
            first_subject_ms=120,
            first_proof_ms=4200,
            novelty_score=0.88,
            estimated_cost=0.20,
            estimated_runtime_seconds=100.0,
        ),
        estimated_value=3.8,
        exploration=True,
        opening_line="They enforced the rule perfectly until one detail surfaced.",
        payoff_line="That hidden detail forced them to reverse the entire decision.",
    )
    blocked = candidate(
        "candidate-unsupported-001",
        genome_value=genome(
            "genome-unsupported-001",
            evidence_completeness=0.35,
            media_feasibility=0.30,
            rights_risk="red",
        ),
        evidence_ids=(),
        estimated_value=4.8,
        opening_line="The secret proof changes everything.",
        payoff_line="The secret proof changes everything.",
    )

    candidates = (consequence, proof_first, suspense, blocked)
    tournament = CandidateTournament().run(candidates, context)
    scored = [
        ScoredCandidate(candidate=item, utility=tournament.result.utilities[item.candidate_id])
        for item in candidates
        if item.candidate_id not in tournament.result.blocked_candidate_ids
    ]
    constraints = PortfolioConstraints(
        target_count=2,
        maximum_total_cost=1.0,
        maximum_total_runtime_seconds=400.0,
        maximum_per_topic=2,
        maximum_per_channel={"channel-daily": 2},
        minimum_exploration=1,
        allowed_rights_risks=("green",),
        minimum_evidence_completeness=0.75,
        minimum_media_feasibility=0.60,
    )
    portfolio = PortfolioPlanner().plan(scored, constraints)

    counterfactuals = CounterfactualRunner(TransparentHeuristicPredictor()).run(
        consequence,
        (
            CounterfactualChange(
                name="move-proof-to-first-frame",
                genome_updates={"first_proof_ms": 0, "first_subject_ms": 0},
                rationale="Test proof-first timing without changing the premise.",
            ),
            CounterfactualChange(
                name="delay-payoff",
                genome_updates={"reveal_position": 0.90},
                rationale="Make the information gap larger while preserving all other fields.",
            ),
        ),
    )

    return {
        "scope": {
            "production_modified": False,
            "publishing_enabled": False,
            "network_calls": False,
            "synthetic_fixture": True,
        },
        "tournament": tournament.result,
        "evaluations": tournament.evaluations,
        "portfolio": portfolio,
        "counterfactuals": counterfactuals,
    }


def command_demo(state_dir: Optional[Path]) -> int:
    result = build_demo()
    if state_dir is not None:
        ledger = FileLedger(state_dir / "professional_media_os_demo.jsonl")
        ledger.append("demo.completed", to_primitive(result))
        count, head_hash = ledger.verify()
        result = dict(result)
        result["ledger"] = {
            "path": str(ledger.path),
            "event_count": count,
            "head_hash": head_hash,
        }
    print(json.dumps(to_primitive(result), indent=2, sort_keys=True))
    return 0


def command_verify_ledger(state_dir: Path) -> int:
    ledger = FileLedger(state_dir / "professional_media_os_demo.jsonl")
    count, head_hash = ledger.verify()
    print(
        json.dumps(
            {
                "valid": True,
                "event_count": count,
                "head_hash": head_hash,
                "path": str(ledger.path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Isolated Professional Media OS reference CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo", help="Run a synthetic in-memory demonstration")
    demo_parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Optional explicit prototype-only directory for a hash-chained demo ledger",
    )

    verify_parser = subparsers.add_parser(
        "verify-ledger",
        help="Verify a previously written prototype demo ledger",
    )
    verify_parser.add_argument("--state-dir", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        return command_demo(args.state_dir)
    if args.command == "verify-ledger":
        return command_verify_ledger(args.state_dir)
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
