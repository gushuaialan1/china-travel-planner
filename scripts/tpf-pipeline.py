#!/usr/bin/env python3
"""
tpf-pipeline.py - Run the full travel page generation pipeline.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SEARCH_SCRIPT = REPO_ROOT / "scripts" / "search_travel_info.py"
GENERATE_SCRIPT = REPO_ROOT / "page-generator" / "scripts" / "tpf-generate.py"
CLI_SCRIPT = REPO_ROOT / "page-generator" / "scripts" / "tpf-cli.py"


def error(msg: str) -> None:
    print(f"[tpf-pipeline] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    print(f"[tpf-pipeline] {msg}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="tpf-pipeline",
        description="Run the full travel page generation pipeline.",
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--from-json", help="Read structured input JSON from file")
    input_group.add_argument("--from-stdin", action="store_true", help="Read structured input JSON from stdin")
    parser.add_argument(
        "--output-dir",
        "-d",
        default=".",
        help="Output directory for the generated project (default: current directory)",
    )
    parser.add_argument("--skip-search", action="store_true", help="Skip the travel info search step")
    parser.add_argument("--skip-validate", action="store_true", help="Skip the validation step")
    parser.add_argument("--with-metro", action="store_true", help="Pass through to tpf-generate")
    parser.add_argument("--with-images", action="store_true", help="Pass through to tpf-generate")
    parser.add_argument("--pretty", action="store_true", help="Pass through to tpf-generate")
    parser.add_argument("--deploy", action="store_true", help="Deploy after a successful build")
    return parser.parse_args()


def load_input_data(args: argparse.Namespace) -> dict:
    if args.from_json:
        input_path = Path(args.from_json).expanduser().resolve()
        try:
            return json.loads(input_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            error(f"Input JSON file not found: {input_path}")
        except json.JSONDecodeError as exc:
            error(f"Invalid JSON in {input_path}: {exc}")

    raw = sys.stdin.read().strip()
    if not raw:
        error("No JSON content received from stdin")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        error(f"Invalid JSON from stdin: {exc}")


def should_run_search(args: argparse.Namespace, input_data: dict) -> bool:
    if args.skip_search:
        info("Search step skipped: --skip-search was provided")
        return False
    if not os.environ.get("TAVILY_API_KEY"):
        info("Search step skipped: TAVILY_API_KEY is not set")
        return False
    attractions = input_data.get("attractions")
    if not isinstance(attractions, list) or not attractions:
        info("Search step skipped: input has no attractions")
        return False
    return True


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_command(cmd: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        error(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")


def main() -> None:
    args = parse_args()
    input_data = load_input_data(args)

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    trip_data_path = data_dir / "trip-data.json"
    travel_info_path = data_dir / "travel-info.json"

    steps: list[tuple[str, callable]] = []

    with tempfile.TemporaryDirectory(prefix="tpf-pipeline-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        pipeline_input_path = temp_dir / "input.json"
        write_json(pipeline_input_path, input_data)

        if should_run_search(args, input_data):
            def step_search() -> None:
                run_command(
                    [
                        "python3",
                        str(SEARCH_SCRIPT),
                        "--from-json",
                        str(pipeline_input_path),
                        "--output",
                        str(travel_info_path),
                        "--pretty",
                    ]
                )

            steps.append(("Searching travel info", step_search))

        def step_generate() -> None:
            cmd = [
                "python3",
                str(GENERATE_SCRIPT),
                "--from-json",
                str(pipeline_input_path),
                "--output",
                str(trip_data_path),
            ]
            if args.with_metro:
                cmd.append("--with-metro")
            if args.with_images:
                cmd.append("--with-images")
            if args.pretty:
                cmd.append("--pretty")
            run_command(cmd)

        steps.append(("Generating trip-data.json", step_generate))

        if not args.skip_validate:
            def step_validate() -> None:
                run_command(["python3", str(CLI_SCRIPT), "validate"], cwd=output_dir)

            steps.append(("Validating trip-data.json", step_validate))
        else:
            info("Validation step skipped: --skip-validate was provided")

        def step_build() -> None:
            run_command(["python3", str(CLI_SCRIPT), "build"], cwd=output_dir)

        steps.append(("Building page", step_build))

        if args.deploy:
            def step_deploy() -> None:
                run_command(["python3", str(CLI_SCRIPT), "deploy"], cwd=output_dir)

            steps.append(("Deploying page", step_deploy))

        total_steps = len(steps)
        for index, (label, func) in enumerate(steps, start=1):
            info(f"Step {index}/{total_steps}: {label}...")
            func()

    final_output_path = output_dir / "dist" / "index.html"
    info(f"Final output path: {final_output_path}")


if __name__ == "__main__":
    main()
