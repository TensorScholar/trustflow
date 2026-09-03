from __future__ import annotations

import argparse

from trustflow.adapters.generator import ExtractiveAnswerGenerator
from trustflow.evaluation import adversarial_report_violations, run_adversarial_corpus


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the synthetic adversarial claim corpus.")
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Exit non-zero if any labeled case or release safety metric regresses.",
    )
    args = parser.parse_args()

    report = run_adversarial_corpus(generator=ExtractiveAnswerGenerator())
    print(report.model_dump_json(indent=2))
    if args.require_clean and (violations := adversarial_report_violations(report)):
        for violation in violations:
            print(f"adversarial gate violation: {violation}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
