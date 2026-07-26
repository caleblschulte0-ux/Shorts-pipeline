from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from .closure import build_closure_report, write_closure_artifact
from .fixtures import FIXED_TODAY, golden_story
from .models import Fault
from .pipeline import CompletionPipeline
from .registry import complete_test_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the isolated channel completion lab")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fault", choices=[fault.value for fault in Fault], default=Fault.NONE.value)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as temp:
        result = CompletionPipeline(Path(temp), today=FIXED_TODAY).run(golden_story(), fault=Fault(args.fault))
    report = build_closure_report(complete_test_evidence())
    payload = {
        "pipeline_status": result.status.value,
        "pipeline_reasons": list(result.reasons),
        "isolated_scope_percent": report.overall_percent,
        "production_pipeline_modified": False,
    }
    if args.output:
        write_closure_artifact(args.output, report)
    print(json.dumps(payload, sort_keys=True))
    return 0 if result.status.value == "shipped" else 2


if __name__ == "__main__":
    raise SystemExit(main())
