"""Generate, score and select promo clips from parsed episodes."""
from dataclasses import dataclass, field

from . import heuristics as H
from .parse import fmt

MIN_LEN, MAX_LEN = 20.0, 60.0


@dataclass
class Segment:
    episode: int
    start: float
    end: float

    @property
    def length(self):
        return self.end - self.start

    def to_dict(self):
        return {"episode": self.episode, "start": fmt(self.start), "end": fmt(self.end),
                "seconds": round(self.length, 2)}


@dataclass
class Promo:
    kind: str                       # continuous | stitched
    segments: list
    scores: dict
    score: float
    hook_event: object = None
    cliff_line: object = None
    cliff_beat: object = None
    hook: str = ""
    cliffhanger: str = ""
    why: str = ""
    judged_by: str = "heuristic"
    flags: list = field(default_factory=list)

    @property
    def length(self):
        return sum(s.length for s in self.segments)

    @property
    def main(self):
        return self.segments[-1]   # the body that carries the cliffhanger


def cut_points(ep):
    """Shot boundaries that do not slice through a spoken line."""
    pts = {0.0}
    for sh in ep.shots:
        pts.add(round(sh.start, 2))
        pts.add(round(sh.end, 2))
    lines = ep.lines

    def ok(t):
        return not any(l.start < t - 0.15 and l.end > t + 0.15 for l in lines)
    return sorted(t for t in pts if ok(t))


class EpisodeScorer:
    """Caches per-boundary scores for one episode."""

    def __init__(self, ep):
        self.ep = ep
        self.events = ep.events
        self.cuts = cut_points(ep)
        self.end = ep.duration
        self._hook, self._cliff = {}, {}

    def hook(self, s):
        if s not in self._hook:
            self._hook[s] = H.hook_score(self.events, s)
        return self._hook[s]

    def cliff(self, e):
        if e not in self._cliff:
            self._cliff[e] = H.cliff_score(self.events, e, self.end)
        return self._cliff[e]

    def score_window(self, s, e):
        hook, hev = self.hook(s)
        cliff, cline, cbeat = self.cliff(e)
        scores = {"hook": round(hook, 3), "cliffhanger": round(cliff, 3),
                  "standalone": round(H.standalone_score(self.events, s, e), 3),
                  "intensity": round(H.intensity_score(self.events, s, e), 3)}
        return Promo("continuous", [Segment(self.ep.number, s, e)], scores,
                     H.combine(scores, e - s), hev, cline, cbeat)

    def all_windows(self):
        out = []
        for i, s in enumerate(self.cuts):
            for e in self.cuts[i + 1:]:
                if e - s > MAX_LEN:
                    break
                if e - s >= MIN_LEN:
                    out.append(self.score_window(s, e))
        return out

    def hook_beats(self, max_len=7.0):
        """Short (2-7 s) shot-aligned moments with a strong opening, for stitched promos."""
        beats = []
        for i, s in enumerate(self.cuts):
            hook, hev = self.hook(s)
            if not hev or hook < 0.6:
                continue
            for e in self.cuts[i + 1:]:
                if e - s > max_len:
                    break
                if e - s >= 2.0 and e >= hev.end - 0.05:
                    beats.append((hook, Segment(self.ep.number, s, e), hev))
                    break
        return sorted(beats, key=lambda b: -b[0])


def overlap(a, b):
    if a.episode != b.episode:
        return 0.0
    inter = max(0.0, min(a.end, b.end) - max(a.start, b.start))
    return inter / max(1e-6, min(a.length, b.length))


def select(cands, k, floor_ratio=0.8, max_overlap=0.25):
    """Greedy non-overlapping top-k, dropping picks far below the best."""
    picked = []
    for c in sorted(cands, key=lambda p: -p.score):
        if picked and c.score < floor_ratio * picked[0].score:
            break
        if all(overlap(c.main, p.main) <= max_overlap for p in picked):
            picked.append(c)
        if len(picked) == k:
            break
    return picked


def make_stitched(base, scorers, ep_num):
    """Prepend a stronger hook beat (same or previous episode) to a promo with a weak opening."""
    if base.scores["hook"] >= 0.6 or base.scores["cliffhanger"] < 0.5:
        return None
    body = base.main
    sc = scorers[ep_num]
    best = None
    for src in (ep_num, ep_num - 1):
        if src not in scorers:
            continue
        for hook, beat, hev in scorers[src].hook_beats():
            if src == ep_num and not (beat.end <= body.start or beat.start >= body.end + 10):
                continue  # overlaps the body, or would spoil what happens right after it
            # trim the body's start so the whole promo fits in 60 s
            starts = [t for t in sc.cuts if body.start <= t and body.end - t >= 15.0
                      and beat.length + body.end - t <= MAX_LEN]
            if not starts:
                continue
            s = starts[0]
            if beat.length + body.end - s < MIN_LEN:
                continue
            trimmed = sc.score_window(s, body.end)
            scores = dict(trimmed.scores)
            scores["hook"] = round(hook, 3)
            scores["standalone"] = round(scores["standalone"] * 0.9, 3)  # a jump cut costs clarity
            total = H.combine(scores, beat.length + body.end - s)
            if total > base.score + 0.03 and (best is None or total > best.score):
                best = Promo("stitched", [beat, Segment(ep_num, s, body.end)], scores, total,
                             hev, trimmed.cliff_line, trimmed.cliff_beat)
            break  # beats are sorted; the best usable one per source episode is enough
    return best


def find_promos(episodes, per_episode=3):
    scorers = {ep.number: EpisodeScorer(ep) for ep in episodes}
    promos = []
    pools = {}
    for ep in episodes:
        cands = scorers[ep.number].all_windows()
        pools[ep.number] = cands
        picked = select(cands, per_episode)
        stitched = [st for st in (make_stitched(p, scorers, ep.number) for p in picked) if st]
        if stitched:
            picked.append(max(stitched, key=lambda p: p.score))
        promos.extend(picked)
    return promos, scorers, pools
