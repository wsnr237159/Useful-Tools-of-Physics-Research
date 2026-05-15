#!/usr/bin/env python3
"""Sample standalone script for the research tools launcher."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Echo sample parameters.")
    parser.add_argument("--message", required=True, help="Message to print.")
    parser.add_argument("--repeat", type=int, default=1, help="Number of repetitions.")
    parser.add_argument(
        "--mode",
        choices=("summary", "detailed"),
        default="summary",
        help="Output verbosity.",
    )
    parser.add_argument("--write-file", action="store_true", help="Write a sample output file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(os.environ.get("PHYSICS_TOOLS_OUTPUT_DIR", ".")).resolve()

    print("Sample Echo")
    print(f"Output directory: {output_dir}")
    for index in range(max(args.repeat, 0)):
        print(f"{index + 1}: {args.message}")

    if args.mode == "detailed":
        print(f"Message length: {len(args.message)}")
        print(f"Repeat count: {args.repeat}")

    if args.write_file:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "sample_echo_output.txt"
        output_file.write_text(
            f"message={args.message}\nrepeat={args.repeat}\nmode={args.mode}\n",
            encoding="utf-8",
        )
        print(f"Wrote: {output_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
