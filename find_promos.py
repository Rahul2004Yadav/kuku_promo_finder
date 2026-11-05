#!/usr/bin/env python3
"""Find ranked promo clips in a microdrama screenplay pack.

  python find_promos.py SCRIPTS_DIR_OR_ZIP --out outputs/
  python find_promos.py SCRIPTS_DIR_OR_ZIP --out outputs/ --llm gemini:gemini-2.5-flash
"""
import argparse
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from promo_finder.candidates import find_promos, make_stitched, select
from promo_finder.llm import LLMError, judge_episode
from promo_finder.parse import load_show
from promo_finder.report import add_flags, describe, rank, write_outputs


def unpack(path, tmp):
    path = Path(path)
    if path.suffix.lower() != ".zip":
        return path
    with zipfile.ZipFile(path) as z:
        for m in z.namelist():
            target = (Path(tmp) / m).resolve()
            if not str(target).startswith(str(Path(tmp).resolve())):
                sys.exit(f"Unsafe path in zip: {m}")
        z.extractall(tmp)
    return Path(tmp)


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

    t0 = time.time()
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
    by_num = {e.number: e for e in episodes}
    print(f"Loaded {len(episodes)} episodes, {sum(len(e.events) for e in episodes)} events.")

    if not args.llm:
        promos, scorers, pools = find_promos(episodes, args.per_episode)
    else:
        # Wider pool per episode, let the model re-score, then keep the best.
        _, scorers, pools = find_promos(episodes, args.pool)
        promos = []
        cache = Path(args.out) / "llm_cache"
        for ep in episodes:
            pool = select(pools[ep.number], args.pool, floor_ratio=0.7)
            pool += [s for s in (make_stitched(p, scorers, ep.number) for p in pool) if s][:2]
            for p in pool:
                add_flags(p, by_num)
                describe(p)
            try:
                judge_episode(args.llm, ep, pool, scorers, by_num, cache_dir=cache)
                print(f"  judged ep{ep.number}")
            except LLMError as e:
                if "is not set" in str(e) or "Unknown provider" in str(e):
                    sys.exit(f"LLM setup error: {e}")
                print(f"  ep{ep.number}: LLM failed ({e}); keeping heuristic scores")
            promos += select(pool, args.per_episode, floor_ratio=0.0)

    for p in promos:
        add_flags(p, by_num)
        describe(p)
    ranked, first_wave = rank(promos)
    settings = {"judge": args.llm or "heuristic (no LLM)", "per_episode": args.per_episode,
                "seconds": round(time.time() - t0, 1)}
    write_outputs(args.out, show, episodes, ranked, first_wave, settings, pools)
    print(f"{len(ranked)} promos -> {args.out}/ (promos.md, promos.csv, promos.json, quality_report.md) "
          f"in {settings['seconds']}s")


if __name__ == "__main__":
    main()
