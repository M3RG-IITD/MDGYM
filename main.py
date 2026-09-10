#!/usr/bin/env python3
"""
Main entry point for MD Simulation Interface.

This provides a command-line interface for solving molecular dynamics problems.
Supports both single-problem mode and batch/session mode.
"""

import argparse
import csv
import sys
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from md_simulation_interface import MDSimulationProblem
from md_simulation_interface.orchestrator import OrchestratorBuilder
from md_simulation_interface.config import Config, setup_logging
from md_simulation_interface.exceptions import MDSimulationError


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="MD Simulation Interface - Solve molecular dynamics problems with AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single problem mode
  python main.py '{"id":"npt","problem_description":"NPT ensemble of Al at 300K","ground_truth":{"temperature":"300","pressure":"1"}}' \\
    --agent claude_code --engine lammps

  # Batch/session mode (folder of JSONs)
  python main.py --input-dir ./data/problems/ --agent claude_code --engine gromacs
  python main.py --input-dir ./data/problems/ --agent claude_code --engine gromacs --session-id my_session

Problem JSON format:
  {
    "id": "npt",
    "problem_description": "...",
    "metrics": ["temperature", "pressure"],
    "ground_truth": {"temperature": "300", "pressure": "1"}
  }

Note: Single-problem runs are saved in working_directory/<problem_id>/
      Session runs are saved in working_directory/<session_id>/<problem_id>/
        """
    )

    parser.add_argument(
        "problem",
        type=str,
        nargs="?",
        default=None,
        help="Problem definition as a JSON string (single-problem mode)"
    )

    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Folder containing JSON problem files (batch/session mode)"
    )

    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Session identifier (optional; auto-generated if not provided, only used with --input-dir)"
    )

    parser.add_argument(
        "--agent",
        type=str,
        choices=["claude_code", "codex", "gemini", "openhands"],
        required=True,
        help="AI agent to use (claude_code, codex, gemini, openhands)"
    )

    parser.add_argument(
        "--engine",
        type=str,
        choices=["lammps", "gromacs"],
        required=True,
        help="MD engine to use (lammps or gromacs)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Timeout for simulation in seconds (default: 900)"
    )

    parser.add_argument(
        "--inter-problem-delay",
        type=int,
        default=60,
        dest="inter_problem_delay",
        help="Seconds to wait between problems to avoid rate limiting (default: 60)"
    )

    parser.add_argument(
        "--script-dir",
        type=str,
        default=None,
        dest="script_dir",
        help=(
            "Post-processing mode: path to a directory containing pre-run simulation files "
            "(LAMMPS input, log, potentials, structures). "
            "In single-problem mode, point directly to the problem's script directory. "
            "In batch mode, point to the base golden-scripts directory — the framework "
            "searches level_1/, level_2/, level_3/ subdirectories for a folder whose name "
            "matches the JSON file stem."
        )
    )

    return parser


def find_script_dir(base: str, problem_name: str) -> str | None:
    """
    Locate a golden-script directory for *problem_name* under *base*.

    Checks, in order:
      base/problem_name/
      base/level_1/problem_name/
      base/level_2/problem_name/
      base/level_3/problem_name/
    Returns the first match, or None if not found.
    """
    root = Path(base)
    candidates = [root / problem_name] + [root / f"level_{n}" / problem_name for n in (1, 2, 3)]
    for c in candidates:
        if c.is_dir():
            return str(c)
    return None


def solve_single(orchestrator, problem_data: dict, args, base_dir: str = None,
                 script_dir: str = None, logger=None):
    """Solve a single problem. Returns (success, result)."""
    problem_id = problem_data.get("id", "unknown")
    description = problem_data["problem_description"]
    ground_truth = problem_data.get("ground_truth")
    required_metrics = problem_data.get("metrics", [])

    # Post-processing mode: fixed 300s (no simulation to run).
    # Full simulation mode: 300 + time_limit from the problem JSON, fallback to --timeout arg.
    if script_dir:
        timeout = 300
        time_limit = None
    else:
        time_limit = problem_data.get("time_limit")
        timeout = 300 + int(time_limit) if time_limit is not None else args.timeout

    if logger:
        logger.info(f"Loaded problem '{problem_id}'")
        if ground_truth:
            logger.info(f"Ground truth values: {ground_truth}")
        mode = "post-processing (script_dir set)" if script_dir else "full simulation"
        logger.info(f"Timeout: {timeout}s (mode={mode}, time_limit={time_limit})")

    problem = MDSimulationProblem(
        problem_id=problem_id,
        description=description,
        engine=args.engine,
        ground_truth=ground_truth,
        required_metrics=required_metrics,
        timeout=timeout,
        base_dir=base_dir,
        script_dir=script_dir,
    )

    if logger:
        logger.info(f"Run ID: {problem.run_id}")
        logger.info(f"Working directory: {problem.working_directory}")
        logger.info("Starting to solve MD simulation problem...")

    result = orchestrator.solve(problem)

    print("\n" + result.to_summary())
    print(f"\nRun files saved to: {problem.working_directory}")

    return result.success, result, problem.run_id, problem.working_directory


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Validate: must provide either problem or --input-dir, not both
    if args.problem is None and args.input_dir is None:
        parser.error("Provide either a problem JSON string or --input-dir.")
    if args.problem is not None and args.input_dir is not None:
        parser.error("Provide either a problem JSON string or --input-dir, not both.")

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    config = Config()
    agent_config = config.get_agent_config(args.agent)
    validator_config = config.get_validator_config(args.engine)

    logger.info(f"Building orchestrator with agent={args.agent}, engine={args.engine}")
    orchestrator = OrchestratorBuilder() \
        .with_agent(args.agent, agent_config) \
        .with_engine(args.engine, validator_config) \
        .build()

    try:
        # ── Single-problem mode ──────────────────────────────────────────────
        if args.problem is not None:
            try:
                problem_data = json.loads(args.problem)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid problem JSON: {e}", file=sys.stderr)
                sys.exit(1)

            success, _, _run_id, _wdir = solve_single(
                orchestrator, problem_data, args,
                base_dir=None,
                script_dir=args.script_dir,
                logger=logger,
            )
            sys.exit(0 if success else 1)

        # ── Batch / session mode ─────────────────────────────────────────────
        input_dir = Path(args.input_dir)
        if not input_dir.is_dir():
            print(f"Error: --input-dir '{input_dir}' is not a valid directory.", file=sys.stderr)
            sys.exit(1)

        json_files = sorted(input_dir.glob("*.json"))
        if not json_files:
            print(f"No JSON files found in '{input_dir}'.", file=sys.stderr)
            sys.exit(1)

        # Determine session ID
        if args.session_id:
            session_id = args.session_id
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"session_{timestamp}_{uuid.uuid4().hex[:8]}"

        session_dir = Path("working_directory") / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Add file handler so all logs also go to session_dir/session.log
        log_path = session_dir / "session.log"
        file_handler = logging.FileHandler(log_path, mode="w")
        file_handler.setLevel(getattr(logging, args.log_level.upper()))
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logging.getLogger().addHandler(file_handler)

        print(f"\nSession ID : {session_id}")
        print(f"Session dir: {session_dir}")
        print(f"Session log: {log_path}")
        print(f"Problems   : {len(json_files)} JSON file(s) in '{input_dir}'\n")
        logger.info(f"Session ID: {session_id}, session dir: {session_dir}")

        # Results CSV is updated on-the-fly (one row per problem, flushed immediately)
        # rather than collected in memory and written at the end, so progress survives
        # an interruption instead of being lost.
        csv_path = session_dir / "results.csv"
        csv_is_new = not csv_path.exists()
        csv_file = csv_path.open("a", newline="")
        csv_writer = csv.writer(csv_file)
        if csv_is_new:
            csv_writer.writerow(["run_id", "problem_id", "success", "produced_answer", "score", "execution_time"])
            csv_file.flush()

        # (json_file_name, success, score, message)
        results_summary = []
        overall_success = True

        for idx, json_file in enumerate(json_files, start=1):
            print(f"[{idx}/{len(json_files)}] Processing: {json_file.name}")
            logger.info(f"[{idx}/{len(json_files)}] Loading problem from {json_file}")

            try:
                problem_data = json.loads(json_file.read_text())
            except json.JSONDecodeError as e:
                print(f"  Skipping {json_file.name}: invalid JSON ({e})", file=sys.stderr)
                results_summary.append((json_file.name, False, 0.0, "Invalid JSON"))
                overall_success = False
                continue

            problem_id = problem_data.get("id", json_file.stem)

            # Resume support: if this problem's directory already exists under the
            # session, a previous (possibly interrupted) run already attempted it —
            # and, if it finished, already has a row in results.csv. Skip re-running
            # so we don't overwrite/lose that progress.
            target_dir = session_dir / problem_id
            if target_dir.is_dir():
                print(f"  [{idx}/{len(json_files)}] '{problem_id}' already present at {target_dir} — skipping")
                logger.info(f"Skipping '{problem_id}': working directory already exists at {target_dir}")
                continue

            try:
                # Resolve golden script dir for this problem (if --script-dir given)
                problem_script_dir = None
                if args.script_dir:
                    problem_name = json_file.stem
                    problem_script_dir = find_script_dir(args.script_dir, problem_name)
                    if problem_script_dir:
                        logger.info(f"Post-processing mode: using script dir {problem_script_dir}")
                    else:
                        logger.warning(
                            f"No script dir found for '{problem_name}' under '{args.script_dir}'. "
                            "Falling back to full simulation mode."
                        )

                success, result, run_id, working_dir = solve_single(
                    orchestrator, problem_data, args,
                    base_dir=str(session_dir),
                    script_dir=problem_script_dir,
                    logger=logger
                )
                last = result.get_last_attempt()
                score = last.score if last else 0.0
                produced_answer = Path(working_dir, "final_answer.json").exists()
                results_summary.append((json_file.name, success, score, "OK" if success else "Failed"))
                csv_writer.writerow((run_id, problem_id, "yes" if success else "no",
                                      "yes" if produced_answer else "no",
                                      f"{score:.4f}",
                                      f"{result.total_execution_time:.2f}"))
                csv_file.flush()
                if not success:
                    overall_success = False
            except Exception as e:
                logger.exception(f"Error solving {json_file.name}: {e}")
                print(f"  Error: {e}", file=sys.stderr)
                results_summary.append((json_file.name, False, 0.0, str(e)))
                csv_writer.writerow(("N/A", problem_id, "no", "no", "0.0000", "0.00"))  # success, produced_answer, score, execution_time
                csv_file.flush()
                overall_success = False

            # Short delay between problems to avoid rate limiting
            if idx < len(json_files):
                delay = args.inter_problem_delay
                print(f"  Waiting {delay}s before next problem...")
                logger.info(f"Inter-problem delay: {delay}s")
                time.sleep(delay)

            # 5-minute break after every 15 problems
            if idx % 15 == 0 and idx < len(json_files):
                print(f"\n[{idx}/{len(json_files)}] Pausing for 5 minutes before continuing...")
                logger.info(f"5-minute break after problem {idx}")
                time.sleep(300)

        csv_file.close()

        # Compute aggregate scores
        total_score = sum(s for _, _, s, _ in results_summary)
        avg_score = total_score / len(results_summary) if results_summary else 0.0
        passed = sum(1 for _, ok, _, _ in results_summary if ok)

        # Build summary lines (shared between console and log)
        summary_lines = [
            "",
            "=" * 60,
            f"Session Summary  [{session_id}]",
            "=" * 60,
        ]
        for name, ok, score, msg in results_summary:
            status = "PASS" if ok else "FAIL"
            summary_lines.append(f"  [{status}]  score={score:.3f}  {name}  —  {msg}")
        summary_lines += [
            "",
            f"  Problems : {len(results_summary)}  |  Passed: {passed}  |  Failed: {len(results_summary) - passed}",
            f"  Total score  : {total_score:.3f}",
            f"  Average score: {avg_score:.3f}",
            f"  Results under: {session_dir}",
            "=" * 60,
        ]

        summary_text = "\n".join(summary_lines)
        print(summary_text)
        logger.info(summary_text)

        print(f"  CSV saved  : {csv_path}")
        logger.info(f"Session CSV saved to: {csv_path}")

        sys.exit(0 if overall_success else 1)

    except MDSimulationError as e:
        logger.exception(f"MD Simulation error: {str(e)}")
        print(f"\nError: {str(e)}", file=sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        logger.exception("Unexpected error occurred")
        print(f"\nUnexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
