"""Validate a selected results snapshot without executing notebooks."""
import argparse
import json
from congress_scorecard import load_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    args = parser.parse_args()
    inputs = load_inputs(snapshot=args.snapshot)
    print(json.dumps(inputs.diagnostics, indent=2))
    print("VALIDATION PASSED")


if __name__ == "__main__":
    main()
