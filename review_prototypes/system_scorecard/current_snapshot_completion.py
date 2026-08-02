from __future__ import annotations

from review_prototypes.completion_lab.closure import build_closure_report
from review_prototypes.completion_lab.registry import complete_test_evidence


def isolated_test_area_completion_snapshot():
    """Return the closure score for the isolated review/test area only.

    Live production wiring and real public-channel performance are deliberately
    outside this scope and are not represented by this 100% score.
    """
    return build_closure_report(complete_test_evidence())
