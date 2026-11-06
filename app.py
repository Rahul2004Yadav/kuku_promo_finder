"""Promo Finder web app.  Run: streamlit run app.py"""
import hashlib
import io
import os
import tempfile
import zipfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from promo_finder.llm import OPENAI_COMPATIBLE, LLMError
from promo_finder.parse import fmt, load_show
from promo_finder.pipeline import run, unpack
from promo_finder.report import post_score, seg_str, write_outputs

HERE = Path(__file__).parent
DEMO = HERE / "demo_show"
PROVIDERS = ["gemini", "groq", "openrouter", "openai", "anthropic", "custom"]
DEFAULT_MODEL = {"gemini": "gemini-2.5-flash", "groq": "llama-3.3-70b-versatile", "anthropic": "claude-sonnet-5-5",
                 "openai": "gpt-4o-mini", "openrouter": "", "custom": ""}
FLAG_HELP = {
    "episode_ending": "ends on the episode's own final cliffhanger (strong, but spoils the ending)",
    "many_characters": "4+ speakers: harder for a stranger to follow",
    "crosses_scenes": "jumps between scenes",
    "weak_ending": "the last beat may feel resolved",
    "BAD_LENGTH": "outside 20–60 s (must not happen)",
    "CUTS_A_LINE": "a cut slices through a spoken line (must not happen)",
}

st.set_page_config(page_title="Promo Finder: microdrama promos", page_icon="🎬", layout="wide")

# Keys set as Streamlit secrets (owner's deployment) behave like environment variables.
try:
    for k, v in st.secrets.items():
        if isinstance(v, str) and k.endswith(("_API_KEY", "_BASE_URL")):
            os.environ.setdefault(k, v)
except Exception:
    pass


def md(text):
    """Streamlit renders $...$ as LaTeX; scripts don't mean that."""
    return str(text).replace("$", "\\$")


@st.cache_data(show_spinner=False)
def load_demo():
    return load_show(DEMO)


@st.cache_data(show_spinner=False, max_entries=4)
def load_upload(data: bytes):
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "upload.zip"
        src.write_bytes(data)
        out = Path(tmp) / "x"
        out.mkdir()
        return load_show(unpack(src, out))


@st.cache_data(show_spinner=False, max_entries=8)
def heuristic(key, per_episode, _episodes):
    return run(_episodes, per_episode, log=lambda *a: None)


def files_for(show, episodes, result):
    ranked, first_wave, settings, pools = result
    with tempfile.TemporaryDirectory() as tmp:
        write_outputs(tmp, show, episodes, ranked, first_wave, settings, pools)
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(Path(tmp).iterdir())}


# ---------------- sidebar ----------------
st.sidebar.title("🎬 Promo Finder")
st.sidebar.caption("Finds 20–60 s promo clips (hook → cliffhanger) in microdrama scripts.")
page = st.sidebar.radio("Page", ["🏆 Post first", "📋 All promos", "🎬 Promo detail", "✅ Quality report",
                                 "📦 Export", "ℹ️ How it works"], label_visibility="collapsed")
st.sidebar.divider()
source = st.sidebar.radio("Scripts", ["Demo show (synthetic)", "Upload a .zip of episode scripts"])
episodes, key, show = [], "", ""
if source.startswith("Demo"):
    episodes, key, show = load_demo(), "demo", "The Glass Heir (synthetic demo)"
else:
    up = st.sidebar.file_uploader("Zip of episode .txt files", type=["zip"])
    if up is not None:
        data = up.getvalue()
        key, show = hashlib.sha1(data).hexdigest()[:12], Path(up.name).stem
        try:
            episodes = load_upload(data)
        except (zipfile.BadZipFile, SystemExit):
            st.sidebar.error("That zip could not be read safely.")

per_episode = st.sidebar.slider("Promos kept per episode", 1, 5, 3)
with st.sidebar.expander("LLM judge (optional)"):
    st.caption("Rules are free and instant. An LLM re-scores the top candidates for nuance and writes the "
               "hook / cliffhanger / why lines. Swap the model with one string.")
    use_llm = st.toggle("Use an LLM judge")
    provider = st.selectbox("Provider", PROVIDERS, disabled=not use_llm)
    model = st.text_input("Model", DEFAULT_MODEL[provider], disabled=not use_llm)
    env_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else OPENAI_COMPATIBLE.get(provider, ("", ""))[1]
    has_env = bool(env_name and os.environ.get(env_name))
    api_key = st.text_input("API key", type="password", disabled=not use_llm,
                            help="Used only for this session; never stored.",
                            placeholder="set on the server" if has_env else "paste your key")
    nums = [e.number for e in episodes] or [1]
    ep_range = st.select_slider("Episodes to judge", options=nums, value=(nums[0], nums[min(4, len(nums) - 1)]),
                                disabled=not use_llm or len(nums) < 2)
    go = st.button("▶ Run with LLM", type="primary", disabled=not use_llm or not episodes)

if not episodes:
    st.title("Promo Finder")
    st.info("Upload a zip of episode scripts in the sidebar, or switch to the demo show.")
    st.stop()

# ---------------- results ----------------
if go:
    chosen = [e for e in episodes if ep_range[0] <= e.number <= ep_range[1]]
    bar = st.progress(0.0, text="Judging…")
    try:
        res = run(chosen, per_episode, f"{provider}:{model}", api_key=api_key or None, log=lambda *a: None,
                  progress=lambda f, n: bar.progress(f, text=f"Judged episode {n}"))
        st.session_state.llm = {"sig": (key, per_episode), "result": res, "episodes": chosen}
    except LLMError as e:
        hint = " Paste an API key above (free keys: aistudio.google.com or console.groq.com)." \
            if "is not set" in str(e) else ""
        st.sidebar.error(f"LLM setup error: {e}.{hint}")
    bar.empty()

llm_state = st.session_state.get("llm")
if use_llm and llm_state and llm_state["sig"] == (key, per_episode):
    result, used_eps = llm_state["result"], llm_state["episodes"]
else:
    result, used_eps = heuristic(key, per_episode, episodes), episodes
ranked, first_wave, settings, pools = result
by_num = {e.number: e for e in used_eps}
rank_of = {id(p): i for i, p in enumerate(ranked, 1)}

st.sidebar.divider()
st.sidebar.caption(f"**{md(show)}**  \n{len(used_eps)} episodes · {len(ranked)} promos · judge: {settings['judge']}")


def promo_card(n, p):
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"#### {n}. {seg_str(p)}")
        c1.caption(f"{p.length:.0f} s · {p.kind} · overall rank #{rank_of[id(p)]}")
        c2.metric("score", f"{p.score:.2f}")
        st.markdown(md(f"**🪝 Hook:** {p.hook}"))
        st.markdown(md(f"**🧗 Cliffhanger:** {p.cliffhanger}"))
        st.markdown(md(f"**💡 Why:** {p.why}"))
        if p.flags:
            st.caption("Flags: " + " · ".join(f"`{f}` {FLAG_HELP.get(f, '')}" for f in p.flags))


def post_first():
    st.title("🏆 What to post first")
    st.caption(md(f"{show} · best promo per episode, ranked (early episodes get a small boost: they send new "
                  "viewers to episode 1 with less spoiled)."))
    c = st.columns(4)
    c[0].metric("Episodes", len(used_eps))
    c[1].metric("Promos found", len(ranked))
    c[2].metric("Stitched", sum(p.kind == "stitched" for p in ranked))
    c[3].metric("Hard-rule breaks", sum(f in ("BAD_LENGTH", "CUTS_A_LINE") for p in ranked for f in p.flags))
    for n, p in enumerate(first_wave, 1):
        promo_card(n, p)


def all_promos():
    st.title("📋 All promos, ranked")
    rows = [{"rank": i, "segments": seg_str(p), "seconds": round(p.length, 1), "type": p.kind,
             "score": p.score, "post score": post_score(p), "hook": p.hook, "cliffhanger": p.cliffhanger,
             "flags": " ".join(p.flags), "episode": p.main.episode} for i, p in enumerate(ranked, 1)]
    df = pd.DataFrame(rows)
    eps = st.multiselect("Episode", sorted(df.episode.unique()))
    if eps:
        df = df[df.episode.isin(eps)]
    st.dataframe(df.drop(columns=["episode"]), hide_index=True, width="stretch", height=560,
                 column_config={"score": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
                                "hook": st.column_config.TextColumn(width="large"),
                                "cliffhanger": st.column_config.TextColumn(width="large")})


def detail():
    st.title("🎬 Promo detail")
    n = st.selectbox("Promo", range(1, len(ranked) + 1),
                     format_func=lambda i: f"#{i} · {seg_str(ranked[i - 1])} · {ranked[i - 1].score:.2f}")
    p = ranked[n - 1]
    left, right = st.columns([3, 2])
    with left:
        promo_card(n, p)
    with right:
        sc = pd.DataFrame([{"part": k, "score": v} for k, v in p.scores.items()
                           if k in ("hook", "cliffhanger", "standalone", "intensity")])
        st.altair_chart(alt.Chart(sc).mark_bar().encode(
            x=alt.X("score:Q", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("part:N", sort=None, title=None, axis=alt.Axis(labelOverlap=False)),
            tooltip=["part", alt.Tooltip("score:Q", format=".2f")]).properties(height=210, title="Rule scores"),
            width="stretch")
    st.subheader("The clip, as written")
    for k, seg in enumerate(p.segments, 1):
        ep = by_num[seg.episode]
        st.markdown(f"**Segment {k}: Ep{seg.episode} {fmt(seg.start)}–{fmt(seg.end)}** ({seg.length:.1f} s)")
        rows = []
        for e in ep.events:
            if e.end <= seg.start or e.start >= seg.end:
                continue
            who = e.speaker.title() if e.kind == "dialogue" else e.kind.upper()
            mark = "🪝 first 3 s" if k == 1 and e.start < seg.start + 3 else ""
            rows.append({"time": fmt(e.start), "": mark, "who": who,
                         "tone": ", ".join(e.tones), "text": e.text})
        if rows:
            rows[-1][""] = rows[-1][""] or "🧗 ends here"
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={"text": st.column_config.TextColumn(width="large")})


def quality():
    st.title("✅ Quality report")
    st.markdown(md(files_for(show, used_eps, result)["quality_report.md"]).replace("# Automatic quality report", ""))
    st.info("Where it picks badly: rules can't see acting or picture quality, and they favour loud, dialogue-heavy "
            "beats. An editor checks the top of the list against the footage before posting.")


def export():
    st.title("📦 Export")
    files = files_for(show, used_eps, result)
    what = {"promos.csv": "ranked list for a spreadsheet", "promos.json": "everything, machine-readable",
            "promos.md": "readable shortlist for the editor", "quality_report.md": "hard checks and weak spots"}
    for fn, body in files.items():
        c1, c2 = st.columns([1, 3])
        c1.download_button(f"⬇ {fn}", body, file_name=fn, width="stretch")
        c2.caption(what.get(fn, ""))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fn, body in files.items():
            z.writestr(fn, body)
    st.download_button("⬇ Download all (zip)", buf.getvalue(), file_name="promos.zip", type="primary")


def how():
    st.title("ℹ️ How it works")
    st.markdown("""
**A promo** is a 20–60 s clip that stops a scrolling viewer in the first 3 seconds (a slap, a reveal, a shocking
line), ends on an unresolved moment, and makes sense to someone who has never seen the show.

1. **Parse** each episode into timed events: shots, actions, sound effects, lines with the writers' tone tags.
2. **Cut points**: only on shot boundaries that don't slice a spoken line.
3. **Score every 20–60 s window** with four free rules, each 0–1:
   - *Hook*: the strongest beat in the first 3 s. A reply ("And…", "Yes…") is penalised because it needs context.
   - *Cliffhanger*: the last line is a question, threat or reveal, or the clip ends on an ominous sound or a cut to black.
   - *Standalone*: one scene, few speakers, few backstory words.
   - *Intensity*: the top moments inside.
4. **Pick** the best non-overlapping windows per episode. A *stitched* promo puts a short hook beat in front of a body.
5. **Optional LLM judge** re-scores the top candidates and may tighten the cut. It can only point at real
   event IDs: code snaps them to real cuts, enforces 20–60 s, and drops any quote that isn't in the script.
6. **Rank**: early episodes get a small boost. The *post first* list has one promo per episode, so the first week is varied.

**Human in the loop:** an editor approves the shortlist against the footage.
""")


{"🏆 Post first": post_first, "📋 All promos": all_promos, "🎬 Promo detail": detail,
 "✅ Quality report": quality, "📦 Export": export, "ℹ️ How it works": how}[page]()
