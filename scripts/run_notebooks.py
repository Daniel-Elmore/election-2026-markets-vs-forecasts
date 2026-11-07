"""Execute the three scorecard notebooks using an explicitly selected snapshot."""
import argparse
import sys
from congress_scorecard.runner import execute_notebooks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output-root", help="Optional explicit parent for snapshot/run output directories")
    parser.add_argument("--timeout", type=int, default=600, help="Per-cell timeout in seconds")
    args = parser.parse_args()
    try:
        directory = execute_notebooks(snapshot=args.snapshot, output_root=args.output_root, timeout=args.timeout)
    except Exception as error:
        print(f"RUN FAILED: {error}", file=sys.stderr)
        return 1
    print(f"RUN SUCCEEDED: {directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
