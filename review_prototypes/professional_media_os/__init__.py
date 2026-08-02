"""Review-only Professional Media OS reference package.

Nothing in this package is imported by production. See the adjacent README and adoption
manifest before selectively porting any contract or algorithm.
"""

from .contracts import (
    Candidate,
    CandidateEvaluation,
    ContentGenome,
    ContractError,
    DecisionRecord,
    EvidenceRef,
    EvaluationFinding,
    EvaluationVerdict,
    ExperimentSpec,
    ExperimentState,
    FunnelStage,
    Maturity,
    PatternRecord,
    PortfolioConstraints,
    PortfolioPlan,
    StageMetrics,
    TournamentResult,
    VideoOutcome,
)

__all__ = [
    "Candidate",
    "CandidateEvaluation",
    "ContentGenome",
    "ContractError",
    "DecisionRecord",
    "EvidenceRef",
    "EvaluationFinding",
    "EvaluationVerdict",
    "ExperimentSpec",
    "ExperimentState",
    "FunnelStage",
    "Maturity",
    "PatternRecord",
    "PortfolioConstraints",
    "PortfolioPlan",
    "StageMetrics",
    "TournamentResult",
    "VideoOutcome",
]

__version__ = "0.1.0-review-only"
