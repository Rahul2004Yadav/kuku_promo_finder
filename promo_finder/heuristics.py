"""Rule-based scoring of a clip window. Free, deterministic, explainable.

Every score is in 0..1. The rules encode the brief's definition of a promo:
hook in the first 3 s, unresolved ending, makes sense without the show.
"""
import re

# Emotion tags the writers put on dialogue, e.g. "(Cold, Commanding)".
HIGH_TONES = re.compile(
    r"scream|shout|shriek|roar|yell|furious|fury|rage|enraged|outrag|venom|cruel|threat|menac|sinister|"
    r"chill|sob|weep|wail|hysteric|terrif|panic|shock|horrif|gloat|taunt|mock|spite|vicious|deadly|"
    r"malic|vindic|vengeful|accus|desperat|brutal|sadist|predator|seeth|contempt|scorn|sneer|triumph|"
    r"incredul|stunned|gasp|anguish|agon|beg|icy|ominous|dangerous|ruthless|savage|unhinged|frantic|"
    r"heartbroken|devastat|shatter|betray|condemn|hiss|snarl|vow")
MID_TONES = re.compile(
    r"cold|stern|firm|defiant|fierce|resolute|desperate|trembl|urgent|smug|command|demand|dismiss|sharp|"
    r"steely|grave|solemn|plead|tearful|breathless|bitter|harsh|arrogant|condescend|calculat|dark|grim|"
    r"alarm|scheming|warning|authoritative|pained|broken|choked|anxious|tense|suspicious")
LOW_TONES = re.compile(
    r"gentle|soft|tender|warm|loving|reassur|calm|relieved|grateful|peaceful|playful|amused|fond|comfort|"
    r"caring|sooth|sweet|smil|laugh|polite|intimate|humble|respectful|curious|reflective")

# Story words that stop a scroll.
STRONG_WORDS = re.compile(
    r"\b(slap\w*|blood\w*|dead|death|die[ds]?|dying|kill\w*|murder\w*|poison\w*|arsenic|knife|dagger|"
    r"sword|blade|gun|fire|burn\w*|flames?|scar\w*|pregnan\w*|baby|heir|divorce|betray\w*|liar|lies|"
    r"traitor|thief|stole|arrest\w*|hang\w*|execut\w*|guilty|prison|dungeon|witch|whore|harlot|"
    r"marry|married|marriage|wedding|bride|groom|annul\w*|disown\w*|inherit\w*|secret\w*|truth|confess\w*|"
    r"duke|duchess|crown|king|queen|revenge|ruin\w*|destroy\w*|never|curse\w*|monster|beast|"
    r"kneel|beg|nothing|worthless|shame\w*|disgrace\w*|scandal\w*)\b", re.I)

# Physical beats in ACTION / CAMERA / SOUND FX text.
VISUAL_HOOK = re.compile(
    r"\b(slap\w*|strik\w*|struck|hits?|punch\w*|shov\w*|grab\w*|seiz\w*|chok\w*|drag\w*|kick\w*|throws?|"
    r"hurl\w*|collaps\w*|falls?|blood\w*|wound\w*|knife|dagger|sword|blade|fire|flames?|crash\w*|"
    r"shatter\w*|smash\w*|explo\w*|burst\w*|slam\w*|scream\w*|tears? (?:off|open)|rips?|kiss\w*|"
    r"faint\w*|branding|iron|arrest\w*|guards?)\b", re.I)
LOUD_SFX = re.compile(r"\b(slap\w*|crash\w*|shatter\w*|scream\w*|bang\w*|explo\w*|slam\w*|gunshot|"
                      r"thunder\w*|smash\w*|roar\w*|shriek\w*|sting)\b", re.I)
REACTION = re.compile(r"\b(gasp\w*|horror|horrified|shock\w*|stunned|freez\w*|widen\w*|tears)\b", re.I)
CLIFF_FX = re.compile(r"cliffhanger|ominous|drone|sting|gasp|crash|thunder|bang|scream|shatter|"
                      r"swell|dramatic|cut to black|slam|freez|widen|stunned|horror|shock|"
                      r"reveal|burst|silhouette|looms?|menac|sinister|unaware", re.I)
RESOLVED_FX = re.compile(r"\b(tender|warm|relie[fv]|smil|laugh|embrace|peaceful|gentle|hug|sigh of relief|"
                         r"fades? out gently|serene|comfort)", re.I)

THREAT = re.compile(r"\b(will|won't|never|unless|if you|before|you'll|i swear|mark my words|or else|"
                    r"dare|until|soon|tomorrow|tonight|pay for|regret|end you|last time)\b", re.I)
REVEAL = re.compile(r"\b(is (?:my|your|the|not)|truth|secret|who you are|it was|you are|i am|"
                    r"pregnant|dead|alive|real|knew|know what|the duke|my wife|my husband)\b", re.I)
CLOSURE = re.compile(r"^(yes|yes\.|thank you|thanks|good|fine|of course|goodbye|goodnight|agreed|very well|"
                     r"as you wish|i understand|okay|alright)\b[.!]?$", re.I)
REPLY_OPENER = re.compile(r"^(and|but|so|yes|no|because|then|well|that|which|it|he|she|they|this|"
                          r"his|her|their|those|these|exactly|indeed|right|then)\b", re.I)
BACKSTORY = re.compile(r"\b(remember|yesterday|last night|earlier|as i said|that night|you promised|"
                       r"again|still|once more|the letter|what happened)\b", re.I)


def tone_level(tones):
    t = " ".join(tones)
    if HIGH_TONES.search(t):
        return 1.0
    if MID_TONES.search(t):
        return 0.6
    if LOW_TONES.search(t):
        return 0.1
    return 0.35


def event_intensity(ev):
    """How much a single event grabs attention, 0..1."""
    if ev.kind == "dialogue":
        words = min(1.0, 0.4 * len(STRONG_WORDS.findall(ev.text)))
        punct = 0.25 if "!" in ev.text else 0.15 if "?" in ev.text else 0.0
        return min(1.0, 0.55 * tone_level(ev.tones) + 0.35 * words + punct)
    physical, reaction = VISUAL_HOOK.search(ev.text), REACTION.search(ev.text)
    if ev.kind == "sfx":
        physical = LOUD_SFX.search(ev.text)  # "a finger striking parchment" is not a hook
    if ev.kind == "camera":
        return 0.6 if physical else 0.35 if reaction else 0.15
    return 0.85 if physical else 0.5 if reaction else 0.25  # action / sfx


def _in(events, a, b, kinds=None):
    return [e for e in events if e.start >= a - 1e-6 and e.start < b and (kinds is None or e.kind in kinds)]


def hook_score(events, s):
    """Best beat starting in the first 3 seconds. Returns (score, event or None)."""
    window = _in(events, s, s + 3.0, {"dialogue", "action", "sfx", "camera"})
    if not window:
        return 0.0, None
    best = max(window, key=event_intensity)
    score = event_intensity(best)
    spoken = [e for e in window if e.kind == "dialogue"]
    if spoken:
        first = spoken[0]
        if REPLY_OPENER.match(first.text) or first.text.startswith(("...", "…")):
            score *= 0.6  # opens mid-exchange: a newcomer hears an answer, not a hook
        if len(first.text.split()) <= 8 and event_intensity(first) >= 0.6:
            score += 0.1  # short, sharp line
    elif score < 0.6:
        score *= 0.6      # silent, low-energy opening
    return min(1.0, score), best


def cliff_score(events, e, episode_end):
    """How unresolved the last ~6 seconds are. Returns (score, last line or None, last beat or None)."""
    lines = [x for x in events if x.kind == "dialogue" and x.end <= e + 0.05 and x.end >= e - 6.0]
    tail = [x for x in events if x.kind != "dialogue" and x.start < e and x.end > e - 3.5]
    score = 0.0
    last = lines[-1] if lines else None
    if last:
        t = last.text
        if t.rstrip().endswith("?"):
            score += 0.3
        if THREAT.search(t):
            score += 0.3
        if REVEAL.search(t):
            score += 0.25
        if t.rstrip().endswith(("...", "…", "-", "—")):
            score += 0.25
        if "!" in t:
            score += 0.1
        score += 0.25 * tone_level(last.tones)
        if CLOSURE.match(t.strip()) or LOW_TONES.search(" ".join(last.tones)):
            score -= 0.3
    beat = None
    for x in tail:
        if CLIFF_FX.search(x.text):
            score += 0.2 if x.kind != "sfx" else 0.3
            beat = x
        if RESOLVED_FX.search(x.text):
            score -= 0.3
    if episode_end - e <= 3.0:
        score += 0.25  # writers end every episode on a cliffhanger
    return max(0.0, min(1.0, score)), last, beat


def standalone_score(events, s, e):
    span = [x for x in events if x.start >= s - 1e-6 and x.end <= e + 1e-6]
    scenes = len({x.scene for x in span})
    speakers = {x.speaker for x in span if x.kind == "dialogue"}
    score = {1: 1.0, 2: 0.75}.get(scenes, 0.45)
    n = len(speakers)
    score *= 1.0 if 2 <= n <= 3 else 0.75 if n in (1, 4) else 0.55 if n == 5 else 0.4 if n > 5 else 0.5
    talk = sum(x.end - x.start for x in span if x.kind == "dialogue") / max(1e-6, e - s)
    if talk < 0.25:
        score *= 0.7  # mostly silent: hard to follow cold
    refs = sum(len(BACKSTORY.findall(x.text)) for x in span if x.kind == "dialogue")
    score -= 0.08 * refs
    return max(0.0, min(1.0, score))


def intensity_score(events, s, e):
    vals = sorted((event_intensity(x) for x in events
                   if x.start >= s - 1e-6 and x.end <= e + 1e-6 and x.kind != "camera"), reverse=True)
    top = vals[:5]
    return sum(top) / 5.0 if top else 0.0


def duration_factor(d):
    return 1.0 if 25 <= d <= 50 else 0.93


WEIGHTS = {"hook": 0.32, "cliffhanger": 0.33, "standalone": 0.17, "intensity": 0.18}


def combine(scores, duration):
    return round(sum(WEIGHTS[k] * scores[k] for k in WEIGHTS) * duration_factor(duration), 4)
