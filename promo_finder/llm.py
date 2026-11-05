"""Optional LLM judge. Swap models with one string: --llm provider:model.

The model never invents timestamps: it can only point at line IDs from the
transcript we give it, and code snaps those to real shot boundaries and checks
the 20-60 s rule. Quotes it writes are checked against the script.
"""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import heuristics as H
from .candidates import MAX_LEN, MIN_LEN, Segment
from .parse import fmt

OPENAI_COMPATIBLE = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY"),
    "ollama": ("http://localhost:11434/v1/chat/completions", None),
    # Any other OpenAI-compatible endpoint (e.g. one Kuku provides):
    "custom": (os.environ.get("PROMO_LLM_BASE_URL", ""), "PROMO_LLM_API_KEY"),
}

SYSTEM = """You are a senior promo editor for vertical microdrama apps (ReelShort, DramaBox style).
A promo is a 20-60 s clip posted to TikTok/Reels/Shorts to win NEW viewers who have never seen the show.
A great promo: (1) the first 3 seconds stop a scrolling thumb (slap, reveal, shocking line);
(2) it cuts on an unresolved moment so the viewer must know what happens next;
(3) it makes sense to a stranger with no context.
Judge honestly; most clips are not great. Score each 0-10. Reply with JSON only."""

USER_TMPL = """SHOW EPISODE {ep}. Logline: {logline}

TRANSCRIPT (ID [start-end] text):
{transcript}

CANDIDATE PROMOS (segments play in order):
{cands}

For EACH candidate return:
- hook, cliffhanger, standalone: integers 0-10
- hook_text: what happens in the first 3 s, quoting the exact line if it is spoken
- cliffhanger_text: the unresolved moment it cuts on, quoting the exact line if spoken
- why: ONE line on why it works (or why it does not)
- start_id / end_id: OPTIONAL transcript IDs to tighten the LAST segment (start at that event, end after that event).
  Use null to keep the current cut. Only use IDs that appear in the transcript.

Return: {{"candidates": [{{"id": "C1", "hook": 0, "cliffhanger": 0, "standalone": 0, "hook_text": "", "cliffhanger_text": "", "why": "", "start_id": null, "end_id": null}}]}}"""


class LLMError(RuntimeError):
    pass


def _post(url, payload, headers, retries=4):
    body = json.dumps(payload).encode()
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < retries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            raise LLMError(f"HTTP {e.code}: {e.read()[:300]!r}") from e
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(5)
                continue
            raise LLMError(str(e)) from e


def complete(spec, system, user):
    provider, _, model = spec.partition(":")
    if provider == "mock":   # offline plumbing test, not a real judgement
        ids = re.findall(r"^(C\d+):", user, re.M)
        return json.dumps({"candidates": [{"id": i, "hook": 6, "cliffhanger": 6, "standalone": 6,
                                           "hook_text": "", "cliffhanger_text": "", "why": "mock",
                                           "start_id": None, "end_id": None} for i in ids]})
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY") or _missing("ANTHROPIC_API_KEY")
        data = _post("https://api.anthropic.com/v1/messages",
                     {"model": model, "max_tokens": 4000, "system": system,
                      "messages": [{"role": "user", "content": user}]},
                     {"x-api-key": key, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in data.get("content", []))
    if provider not in OPENAI_COMPATIBLE:
        raise LLMError(f"Unknown provider '{provider}'. Use one of: {', '.join(OPENAI_COMPATIBLE)}, anthropic, mock")
    url, key_env = OPENAI_COMPATIBLE[provider]
    if not url:
        raise LLMError("Set PROMO_LLM_BASE_URL for the 'custom' provider")
    headers = {}
    if key_env:
        key = os.environ.get(key_env) or _missing(key_env)
        headers["Authorization"] = f"Bearer {key}"
    data = _post(url, {"model": model, "temperature": 0.2,
                       "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}, headers)
    return data["choices"][0]["message"]["content"]


def _missing(name):
    raise LLMError(f"Environment variable {name} is not set")


def _parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise LLMError(f"No JSON in model reply: {text[:200]!r}")
    return json.loads(m.group(0))


def _transcript(ep):
    out = []
    for e in ep.events:
        txt = e.label() if e.kind == "dialogue" else f"[{e.kind.upper()}] {e.text[:110]}"
        tone = f" ({', '.join(e.tones)})" if e.tones else ""
        if e.kind == "dialogue":
            txt = f'{e.speaker}{tone}: "{e.text}"'
        out.append(f"E{e.idx} [{fmt(e.start)}-{fmt(e.end)}] {txt}")
    return "\n".join(out)


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("’", "'"))


def quotes_ok(text, episodes_by_num, ep_nums):
    """Every quoted phrase the model wrote must exist in the script."""
    corpus = " ".join(_norm(l.text) for n in ep_nums for l in episodes_by_num[n].lines)
    for q in re.findall(r'["“]([^"”]{6,})["”]', text or ""):
        if _norm(q).strip() and _norm(q).strip() not in corpus:
            return False
    return True


def _refine(promo, scorer, start_id, end_id):
    """Map model-chosen event IDs to valid shot cuts. Returns new body Segment or None."""
    ep = scorer.ep
    body = promo.main
    s, e = body.start, body.end
    try:
        if start_id is not None:
            ev = ep.events[int(str(start_id).lstrip("E"))]
            s = max([t for t in scorer.cuts if t <= ev.start + 1e-6], default=s)
        if end_id is not None:
            ev = ep.events[int(str(end_id).lstrip("E"))]
            e = min([t for t in scorer.cuts if t >= ev.end - 0.15], default=e)
    except (ValueError, IndexError):
        return None
    other = sum(seg.length for seg in promo.segments[:-1])
    if e <= s or not (MIN_LEN <= other + e - s <= MAX_LEN):
        return None
    if (s, e) == (body.start, body.end):
        return None
    return Segment(body.episode, s, e)


def judge_episode(spec, ep, promos, scorers, episodes_by_num, cache_dir=None, log=print):
    """Re-score this episode's candidate promos with the model, in place."""
    if not promos:
        return
    cand_lines = []
    for i, p in enumerate(promos, 1):
        segs = " + ".join(f"Ep{s.episode} {fmt(s.start)}-{fmt(s.end)}" for s in p.segments)
        cand_lines.append(f"C{i}: {segs} ({p.length:.1f}s)")
    extra = ""
    other_eps = {s.episode for p in promos for s in p.segments} - {ep.number}
    for n in sorted(other_eps):
        extra += f"\n\nTRANSCRIPT OF EPISODE {n} (for stitched segments):\n{_transcript(episodes_by_num[n])}"
    user = USER_TMPL.format(ep=ep.number, logline=ep.logline, transcript=_transcript(ep) + extra,
                            cands="\n".join(cand_lines))

    raw = None
    cache = None
    if cache_dir:
        key = hashlib.sha1((spec + SYSTEM + user).encode()).hexdigest()[:16]
        cache = Path(cache_dir) / f"ep{ep.number:03d}-{key}.json"
        if cache.exists():
            raw = cache.read_text()
    if raw is None:
        raw = complete(spec, SYSTEM, user)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(raw)
    try:
        verdicts = {v.get("id"): v for v in _parse_json(raw).get("candidates", [])}
    except (LLMError, json.JSONDecodeError) as e:
        log(f"  ep{ep.number}: unreadable model reply, keeping heuristic scores ({e})")
        return

    for i, p in enumerate(promos, 1):
        v = verdicts.get(f"C{i}")
        if not v:
            p.flags.append("llm_no_verdict")
            continue
        try:
            llm = {k: max(0.0, min(10.0, float(v.get(k, 0)))) / 10 for k in ("hook", "cliffhanger", "standalone")}
        except (TypeError, ValueError):
            p.flags.append("llm_bad_scores")
            continue
        new_body = _refine(p, scorers[p.main.episode], v.get("start_id"), v.get("end_id"))
        if new_body is not None:
            heur = scorers[p.main.episode].score_window(new_body.start, new_body.end)
            p.segments[-1] = new_body
            p.cliff_line, p.cliff_beat = heur.cliff_line, heur.cliff_beat
            if p.kind == "continuous":
                p.scores.update(heur.scores)
                p.hook_event = heur.hook_event
            p.flags.append("llm_trimmed")
        elif v.get("start_id") is not None or v.get("end_id") is not None:
            p.flags.append("llm_trim_rejected")
        heur_score = H.combine(p.scores, p.length)
        llm_score = 0.35 * llm["hook"] + 0.40 * llm["cliffhanger"] + 0.25 * llm["standalone"]
        p.scores.update({f"llm_{k}": round(x, 2) for k, x in llm.items()})
        p.score = round(0.6 * llm_score + 0.4 * heur_score, 4)
        ep_nums = {s.episode for s in p.segments}
        for field, attr in (("hook_text", "hook"), ("cliffhanger_text", "cliffhanger"), ("why", "why")):
            txt = (v.get(field) or "").strip()
            if txt and quotes_ok(txt, episodes_by_num, ep_nums):
                setattr(p, attr, txt)
            elif txt:
                p.flags.append(f"llm_{attr}_quote_not_in_script")
        p.judged_by = spec
