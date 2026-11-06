"""The whole run, shared by the CLI (find_promos.py) and the web app (app.py)."""
import sys
import time
import zipfile
from pathlib import Path

from .candidates import find_promos, make_stitched, select
from .llm import LLMError, judge_episode
from .report import add_flags, describe, rank


def unpack(path, tmp):
    """A .zip is extracted into tmp (refusing paths that escape it); a folder is used as is."""
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


def run(episodes, per_episode=3, llm="", pool=6, cache_dir=None, api_key=None, log=print, progress=None):
    """Find, (optionally) judge, describe and rank promos.

    Returns (ranked, first_wave, settings, pools). Raises LLMError for setup problems (no key, bad provider);
    other LLM failures keep the heuristic scores for that episode.
    """
    t0 = time.time()
    by_num = {e.number: e for e in episodes}
    if not llm:
        promos, scorers, pools = find_promos(episodes, per_episode)
    else:
        # Wider pool per episode, let the model re-score, then keep the best.
        _, scorers, pools = find_promos(episodes, pool)
        promos = []
        for i, ep in enumerate(episodes):
            cands = select(pools[ep.number], pool, floor_ratio=0.7)
            cands += [s for s in (make_stitched(p, scorers, ep.number) for p in cands) if s][:2]
            for p in cands:
                add_flags(p, by_num)
                describe(p)
            try:
                judge_episode(llm, ep, cands, scorers, by_num, cache_dir=cache_dir, log=log, api_key=api_key)
                log(f"  judged ep{ep.number}")
            except LLMError as e:
                if "is not set" in str(e) or "Unknown provider" in str(e):
                    raise
                log(f"  ep{ep.number}: LLM failed ({e}); keeping heuristic scores")
            promos += select(cands, per_episode, floor_ratio=0.0)
            if progress:
                progress((i + 1) / len(episodes), ep.number)

    for p in promos:
        add_flags(p, by_num)
        describe(p)
    ranked, first_wave = rank(promos)
    settings = {"judge": llm or "heuristic (no LLM)", "per_episode": per_episode,
                "seconds": round(time.time() - t0, 1)}
    return ranked, first_wave, settings, pools
