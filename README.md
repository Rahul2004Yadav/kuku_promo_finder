# Promo Finder

Reads timestamped microdrama screenplays and returns a ranked shortlist of 20–60 s promo clips
for TikTok / Reels / Shorts. Each promo comes with the episode, the exact start and end of every
segment, the hook, the cliffhanger and one line on why it works.

Kuku AI Generalist Assignment, Problem 1.

## Web app

```bash
pip install -r requirements.txt     # streamlit, pandas, altair (only the web app needs them)
streamlit run app.py
```

It has a built-in **synthetic demo show** (`demo_show/`, an original 4-episode story made by
`demo_show/make_demo.py`), or you can upload a zip of scripts (read in a temporary folder, not kept). The pages are:
Post first, All promos, Promo detail (the clip's script with the hook and the cut marked, plus its scores), Quality report, and Export.
The optional **LLM judge** is in the sidebar: pick a provider, type a model, and paste an API key. The key is used for that
session only. The owner can also set e.g. `GEMINI_API_KEY` in the app's Streamlit secrets.

Deploy on Streamlit Community Cloud: point it at this repo with `app.py` as the main file. No secrets are needed for rules-only mode.

## Run it from the command line

Python 3.9+ and nothing to install (standard library only).

```bash
# Free, offline, deterministic (about 2 s for 50 episodes)
python find_promos.py path/to/scripts.zip --out outputs/

# Same, with an LLM judge re-scoring the top candidates. Swap the model with one string:
export GEMINI_API_KEY=...          # free key from aistudio.google.com
python find_promos.py path/to/scripts.zip --out outputs/ --llm gemini:gemini-2.5-flash

python find_promos.py scripts/ --llm groq:llama-3.3-70b-versatile      # GROQ_API_KEY (free tier)
python find_promos.py scripts/ --llm ollama:llama3.1                   # local, no key
python find_promos.py scripts/ --llm anthropic:claude-sonnet-5-5       # ANTHROPIC_API_KEY
python find_promos.py scripts/ --llm openrouter:<model>                # OPENROUTER_API_KEY
PROMO_LLM_BASE_URL=https://.../v1/chat/completions PROMO_LLM_API_KEY=... \
python find_promos.py scripts/ --llm custom:<model>                    # any OpenAI-compatible API

# Useful options
--episodes 1-10     only some episodes
--per-episode 3     promos kept per episode
--pool 6            candidates per episode sent to the LLM
```

The input can be a folder or a `.zip` of `episode-*.txt` scripts.

Tests (they use made-up scripts, not Kuku content):

```bash
python -m unittest discover tests
```

## Outputs

| File | What it is |
|---|---|
| `promos.md` | Readable: the top 10 to post first, then every promo ranked |
| `promos.csv` | For editors: one row per promo, opens in Sheets or Excel |
| `promos.json` | Full detail, including per-criterion scores and flags |
| `quality_report.md` | Automatic checks: hard-rule violations (should be 0), soft flags, weakest episodes |
| `llm_cache/` | Raw model replies (LLM mode only), so reruns cost nothing |

## How it works

```
scripts ─► parse ─► cut points ─► score every 20–60 s window ─► pick top 3 / episode ─► [LLM judge] ─► rank ─► outputs + QA
            │         │               │                              │                     │
          events    shot edges     hook (first 3 s)               no overlap,          re-scores top 6,
          + tones   that don't     cliffhanger (last 6 s)         + "stitched"         may only cite event IDs;
                    cut a line     standalone, intensity          hook + body          code validates every cut
```

`pipeline.py` runs the steps below. Both the CLI and the web app use it.

1. **Parse** (`parse.py`). Each script becomes timed events: camera shots, dialogue (speaker plus the
   writer's emotion tags, such as "Cold, Menacing"), actions and sound FX.
2. **Cut points** (`candidates.py`). Clips may only start or end on a camera-shot boundary, and never
   inside a spoken line. That is how an editor cuts.
3. **Score** (`heuristics.py`). Every 20–60 s window gets four scores from 0 to 1:
   - *hook*: the strongest beat in the first 3 s (intense tone, charged words, a slap or a crash);
     opening on a reply ("And…", "Yes…") is penalised
   - *cliffhanger*: the last line is a question, threat or reveal, or ends on an ominous sound or
     "cut to black"; calm or closing lines are penalised
   - *standalone*: one scene, 2–3 speakers, enough dialogue, few backstory references
   - *intensity*: the five most intense moments inside the clip
4. **Select**. The top non-overlapping clips per episode. When a good clip has a weak opening, a
   **stitched** version puts a short hook beat (2–7 s, same or previous episode) in front.
5. **LLM judge** (optional, `llm.py`). For each episode, the model sees the transcript and the
   candidates, scores them and writes the copy. Guardrails:
   - it can only refer to event IDs; code snaps them to real shot cuts and rejects anything
     outside 20–60 s
   - any line it quotes must appear in the script, or its text is discarded
   - the final score is 60% model and 40% rules, so one odd reply can't fully overturn the rules
   - on any API failure the run keeps the rule-based result
6. **Rank**. Score plus a small bonus for early episodes, since new viewers start at Ep1 and less is
   spoiled. "Post first" takes one promo per episode, so the first week is varied.

## Limits

- It reads text, not video: it can't judge acting, faces or picture quality, and it assumes the
  script timestamps match the final cut.
- The rules favour conflict. Quiet or romantic episodes score low (Ep8 here).
- It can mistake a defiant but resolved ending for a cliffhanger, and it doesn't detect spoilers.
- Stitched hooks are chosen for intensity, not for a narrative link to the body.

Do not commit the scripts or outputs: they are Kuku's confidential content (see `.gitignore`).
