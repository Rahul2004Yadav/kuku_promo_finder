"""Describe, flag, rank and write promos."""
import csv
import json
from collections import Counter
from pathlib import Path

from . import heuristics as H
from .parse import fmt


def _clip(s, n=160):
    return s if len(s) <= n else s[: n - 1] + "…"


def _name(speaker):
    return " ".join(w[:1].upper() + w[1:].lower() for w in speaker.split())


def _ev_text(ev):
    if ev is None:
        return ""
    if ev.kind == "dialogue":
        tone = f" ({', '.join(ev.tones)})" if ev.tones else ""
        return f'{_name(ev.speaker)}{tone}: "{ev.text}"'
    return f"[{ev.kind}] {ev.text}"


def describe(p):
    """Plain-language hook / cliffhanger / why from the rule features (used when no LLM, or as fallback)."""
    p.hook = p.hook or _clip(_ev_text(p.hook_event))
    cliff = _ev_text(p.cliff_line)
    if p.cliff_beat is not None:
        cliff = f"{cliff} → {p.cliff_beat.text}" if cliff else p.cliff_beat.text
    p.cliffhanger = p.cliffhanger or _clip(cliff, 220)
    if p.why:
        return
    parts = []
    hev = p.hook_event
    if hev is not None and hev.kind == "dialogue":
        parts.append(f"opens cold on {_name(hev.speaker)}'s {', '.join(hev.tones[:2]) or 'sharp'} line")
    elif hev is not None:
        parts.append("opens on a physical beat")
    cl = p.cliff_line.text if p.cliff_line else ""
    if cl.rstrip().endswith("?"):
        parts.append("cuts on an unanswered question")
    elif H.THREAT.search(cl):
        parts.append("cuts on a threat/vow left hanging")
    elif H.REVEAL.search(cl):
        parts.append("cuts on a reveal before the reaction lands")
    else:
        parts.append("cuts before the conflict resolves")
    if "episode_ending" in p.flags:
        parts.append("uses the episode's own cliffhanger")
    if p.kind == "stitched":
        beat, body = p.segments
        if beat.episode == body.episode and beat.start > body.end:
            parts.append("flash-forward opening borrowed from later in the episode")
        else:
            parts.append(f"borrows a stronger opening from Ep{beat.episode}")
    if p.scores["standalone"] >= 0.9:
        parts.append("one scene, few characters: easy to follow cold")
    why = "; ".join(parts)
    p.why = why[:1].upper() + why[1:] + "."


def add_flags(p, episodes_by_num):
    ep = episodes_by_num[p.main.episode]
    body = p.main
    span = [e for e in ep.events if e.start >= body.start - 1e-6 and e.end <= body.end + 1e-6]
    speakers = {e.speaker for e in span if e.kind == "dialogue"}
    flags = []
    if p.scores["hook"] < 0.5:
        flags.append("weak_hook")
    if p.scores["cliffhanger"] < 0.5:
        flags.append("weak_ending")
    if len(speakers) >= 4:
        flags.append("many_characters")
    if len({e.scene for e in span}) > 1:
        flags.append("crosses_scenes")
    first = next((e for e in ep.events if e.kind == "dialogue" and e.start >= p.segments[0].start - 1e-6), None)
    if first and p.segments[0].episode == ep.number and H.REPLY_OPENER.match(first.text):
        flags.append("opens_mid_conversation")
    if ep.duration - body.end <= 3.0:
        flags.append("episode_ending")
    if p.kind == "stitched":
        flags.append("jump_cut")
    if p.score < 0.6:
        flags.append("low_confidence")
    if not (20 <= p.length <= 60):
        flags.append("BAD_LENGTH")
    for seg in p.segments:
        sep = episodes_by_num[seg.episode]
        for t in (seg.start, seg.end):
            if any(l.start < t - 0.15 and l.end > t + 0.15 for l in sep.lines):
                flags.append("CUTS_A_LINE")
    p.flags = sorted(set(p.flags + flags))


def post_score(p):
    """Posting priority. Early-episode promos send new viewers to episode 1 with little spoiled."""
    ep = p.segments[0].episode
    bonus = 0.04 if ep <= 5 else 0.02 if ep <= 15 else 0.0
    return round(p.score + bonus, 4)


def rank(promos):
    ranked = sorted(promos, key=lambda p: -post_score(p))
    used, first_wave = set(), []
    for p in ranked:            # posting order: one per episode, so the first week is varied
        eps = {s.episode for s in p.segments}
        if not eps & used:
            first_wave.append(p)
            used |= eps
        if len(first_wave) == 10:
            break
    return ranked, first_wave


def to_dict(p, rank_no):
    return {"rank": rank_no, "type": p.kind,
            "episodes": sorted({s.episode for s in p.segments}),
            "segments": [s.to_dict() for s in p.segments],
            "total_seconds": round(p.length, 2),
            "hook": p.hook, "cliffhanger": p.cliffhanger, "why": p.why,
            "score": p.score, "post_score": post_score(p), "scores": p.scores,
            "judged_by": p.judged_by, "flags": p.flags}


def seg_str(p):
    return " + ".join(f"Ep{s.episode} {fmt(s.start)}–{fmt(s.end)}" for s in p.segments)


def write_outputs(out_dir, show_name, episodes, ranked, first_wave, settings, pools):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [to_dict(p, i) for i, p in enumerate(ranked, 1)]
    rank_of = {id(p): i for i, p in enumerate(ranked, 1)}
    (out / "promos.json").write_text(json.dumps({
        "show": show_name, "episodes": len(episodes), "settings": settings,
        "post_first": [rank_of[id(p)] for p in first_wave], "promos": rows}, indent=2, ensure_ascii=False))

    with open(out / "promos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "type", "segments", "seconds", "hook", "cliffhanger", "why",
                    "score", "hook_s", "cliff_s", "standalone_s", "intensity_s", "judged_by", "flags"])
        for i, p in enumerate(ranked, 1):
            s = p.scores
            w.writerow([i, p.kind, seg_str(p), round(p.length, 1), p.hook, p.cliffhanger, p.why, p.score,
                        s["hook"], s["cliffhanger"], s["standalone"], s["intensity"], p.judged_by,
                        " ".join(p.flags)])

    md = [f"# Promos: {show_name}", "",
          f"{len(ranked)} promos from {len(episodes)} episodes. Judge: {settings['judge']}.", "",
          "## Post first (best per episode, top 10)", ""]
    for n, p in enumerate(first_wave, 1):
        md += [f"### {n}. {seg_str(p)} ({p.length:.0f}s, {p.kind}, score {p.score:.2f})",
               f"- **Hook:** {p.hook}", f"- **Cliffhanger:** {p.cliffhanger}", f"- **Why:** {p.why}",
               f"- Flags: {', '.join(p.flags) or 'none'}", ""]
    md += ["## All promos, ranked", "", "| # | Segments | s | Type | Score | Flags |", "|---|---|---|---|---|---|"]
    for i, p in enumerate(ranked, 1):
        md.append(f"| {i} | {seg_str(p)} | {p.length:.0f} | {p.kind} | {p.score:.2f} | {' '.join(p.flags)} |")
    (out / "promos.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Automatic quality report: hard checks + where the tool is weakest.
    flags = Counter(f for p in ranked for f in p.flags)
    best = {}
    for p in ranked:
        best[p.main.episode] = max(best.get(p.main.episode, 0), p.score)
    weakest = sorted(best.items(), key=lambda kv: kv[1])[:8]
    no_pick = [e.number for e in episodes if e.number not in best]
    ends = sum("episode_ending" in p.flags for p in ranked)
    q = ["# Automatic quality report", "",
         "## Hard checks (must be zero)",
         f"- Promos outside 20-60 s: {flags.get('BAD_LENGTH', 0)}",
         f"- Cuts that slice through a spoken line: {flags.get('CUTS_A_LINE', 0)}", "",
         "## Soft flags (review these first)"]
    q += [f"- {k}: {v} of {len(ranked)}" for k, v in sorted(flags.items()) if k.islower()]
    q += ["", "## Score distribution",
          f"- Candidate windows scored: {sum(len(v) for v in pools.values())}",
          f"- Promos kept: {len(ranked)} ({sum(p.kind == 'stitched' for p in ranked)} stitched)",
          f"- Score min / median / max: {min(p.score for p in ranked):.2f} / "
          f"{sorted(p.score for p in ranked)[len(ranked) // 2]:.2f} / {max(p.score for p in ranked):.2f}",
          f"- Promos ending on the episode's own final cliffhanger: {ends} of {len(ranked)}",
          "", "## Weakest episodes (best promo score). The tool is least sure here; an editor should look.", ""]
    q += [f"- Ep{n}: {s:.2f}" for n, s in weakest]
    if no_pick:
        q += ["", f"Episodes with no promo: {no_pick}"]
    (out / "quality_report.md").write_text("\n".join(q) + "\n", encoding="utf-8")
