#!/usr/bin/env python3
"""Find ranked promo clips in a microdrama screenplay pack.

  python find_promos.py SCRIPTS_DIR_OR_ZIP --out outputs/
  python find_promos.py SCRIPTS_DIR_OR_ZIP --out outputs/ --llm gemini:gemini-2.5-flash
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

from promo_finder.llm import LLMError
from promo_finder.parse import load_show
from promo_finder.pipeline import run, unpack
from promo_finder.report import write_outputs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="folder of episode .txt scripts, or a .zip of them")
    ap.add_argument("--out", default="outputs", help="output folder")
    ap.add_argument("--per-episode", type=int, default=3, help="max promos kept per episode")
    ap.add_argument("--llm", default=os.environ.get("PROMO_LLM", ""),
                    help="optional judge, provider:model, e.g. gemini:gemini-2.5-flash, "
                         "groq:llama-3.3-70b-versatile, ollama:llama3.1, anthropic:claude-sonnet-5-5")
    ap.add_argument("--pool", type=int, default=6, help="candidates per episode sent to the LLM")
    ap.add_argument("--episodes", default="", help="only these episodes, e.g. 1-10 or 3,7")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        episodes = load_show(unpack(args.input, tmp))
    if args.episodes:
        keep = set()
        for part in args.episodes.split(","):
            a, _, b = part.partition("-")
            keep.update(range(int(a), int(b or a) + 1))
        episodes = [e for e in episodes if e.number in keep]
    if not episodes:
        sys.exit("No episodes found.")
    show = Path(args.input).stem
    print(f"Loaded {len(episodes)} episodes, {sum(len(e.events) for e in episodes)} events.")
    try:
        ranked, first_wave, settings, pools = run(episodes, args.per_episode, args.llm, args.pool,
                                                  cache_dir=Path(args.out) / "llm_cache")
    except LLMError as e:
        sys.exit(f"LLM setup error: {e}")
    write_outputs(args.out, show, episodes, ranked, first_wave, settings, pools)
    print(f"{len(ranked)} promos -> {args.out}/ (promos.md, promos.csv, promos.json, quality_report.md) "
          f"in {settings['seconds']}s")


if __name__ == "__main__":
    main()
