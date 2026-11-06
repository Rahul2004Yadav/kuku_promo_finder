"""Build the synthetic demo show "The Glass Heir" (4 episodes, an original story).

It is written in the same timestamped screenplay format as the real scripts, so the public web app can show
the promo finder working without anyone's confidential scripts. Each episode has a mix of strong beats
(slaps, reveals, threats) and quiet stretches, and ends on a cliffhanger, so the ranking has real choices.

Run:  python demo_show/make_demo.py   (rewrites the .txt files next to this script)
"""
from pathlib import Path


def fmt(t):
    m, s = divmod(round(t, 2), 60)
    return f"{int(m):02d}:{s:05.2f}"


def block(header, t0, t1, text):
    return f"**{header}:**\nStart: ({fmt(t0)}) | End: ({fmt(t1)})\n{text}\n"


def episode(num, logline, continuity, scenes):
    """scenes: [(heading, [(shot_len, camera_text, [(offset, dur, header, text), ...]), ...]), ...]"""
    out = [f"EPISODE NUMBER: Episode {num}", f"EPISODE LOGLINE: {logline}", f"CONTINUITY NOTES: {continuity}",
           "", "--- SCRIPT START ---", ""]
    t = 0.0
    for k, (heading, shots) in enumerate(scenes, 1):
        start, body = t, []
        for length, cam, inner in shots:
            body.append(block("CAMERA", t, t + length, cam))
            for off, dur, header, text in inner:
                quoted = header in ("ACTION", "SOUND FX")
                body.append(block(header, t + off, t + off + dur, text if quoted else f'"{text}"'))
            t = round(t + length, 2)
        out += [f"SCENE {k:02d}", f"Scene heading: {heading}", f"Scene start: {fmt(start)}",
                f"Scene end: {fmt(t)}", "", "Actions and dialogue:", ""] + body
    return "\n".join(out) + "\n"


A, S = "ACTION", "SOUND FX"

EP1 = episode(1,
    "Glassblower's daughter Noor is dragged before the court accused of poisoning the young Earl, and a "
    "masked witness swears she did it.",
    "Series opener.",
    [("INT. GLASS WORKSHOP – NIGHT", [
        (4.0, "Wide shot of a glowing furnace, molten glass turning on an iron pipe.",
         [(0.5, 3.0, A, "Noor shapes a small glass vial, sweat on her brow.")]),
        (3.5, "Close-up of Noor's father coughing into a stained cloth.",
         [(0.3, 2.8, "TOMAS (Weak, Gentle)", "Finish it tomorrow, my girl. Rest.")]),
        (3.5, "Medium shot of Noor smiling at him.",
         [(0.4, 2.6, "NOOR (Warm)", "One more piece, Papa. For the Earl's feast.")]),
        (4.0, "Wide shot as the workshop door crashes open; guards pour in.",
         [(0.2, 1.0, S, "The door slams against the wall."),
          (1.2, 2.5, "CAPTAIN REYES (Shouting)", "Noor Ashby! You are under arrest!")]),
        (3.0, "Close-up of the glass vial slipping from Noor's hand and shattering.",
         [(0.2, 1.2, S, "Glass shatters on stone.")]),
        (3.5, "Medium shot of Noor, stunned, as a guard seizes her arm.",
         [(0.3, 2.8, "NOOR (Shocked)", "Arrest? For what?")]),
        (4.0, "Close-up of Captain Reyes holding up a cracked glass bottle.",
         [(0.4, 3.2, "CAPTAIN REYES (Cold)", "The Earl drank poison from your glass. He is dying.")]),
    ]),
     ("INT. GREAT HALL – NIGHT", [
        (5.0, "Wide shot of the torch-lit hall, nobles lining the walls, Noor forced to her knees.",
         [(0.5, 4.0, A, "Guards shove Noor down before the high seat.")]),
        (4.0, "Medium shot of Lady Corvina rising from the high seat in black silk.",
         [(0.5, 3.2, "LADY CORVINA (Icy, Menacing)", "My son lies dying because of your filthy hands.")]),
        (3.5, "Close-up of Noor looking up, defiant.",
         [(0.3, 2.9, "NOOR (Defiant)", "I made the glass. I never filled it.")]),
        (2.5, "Close-up as Lady Corvina's hand strikes Noor across the face.",
         [(0.2, 0.6, S, "A sharp slap echoes through the hall."),
          (0.8, 1.5, A, "Noor's head snaps to the side; blood on her lip.")]),
        (4.0, "Medium shot of Lady Corvina turning to the crowd.",
         [(0.5, 3.2, "LADY CORVINA (Triumphant)", "Then let the witness speak.")]),
        (4.5, "Wide shot as a figure in a silver mask steps out of the crowd.",
         [(0.5, 3.5, A, "Whispers ripple through the nobles.")]),
        (4.0, "Close-up of the silver mask, eyes glinting behind it.",
         [(0.5, 3.2, "MASKED WITNESS (Low, Sinister)", "I saw her pour it. With my own eyes.")]),
        (4.0, "Extreme close-up of Noor's eyes widening in horror.",
         [(0.4, 3.0, "NOOR (Horrified)", "You're lying! Who are you?")]),
        (4.0, "Slow push-in on the mask as the witness leans close to Noor's ear.",
         [(0.5, 3.0, "MASKED WITNESS (Whispering, Cruel)", "Someone you buried, Noor.")]),
        (3.0, "Black screen.",
         [(0.2, 2.6, S, "An ominous drone swells to a cliffhanger sting. Cut to black.")]),
    ])])

EP2 = episode(2,
    "Locked in the tower, Noor learns the dying Earl drank from a glass she never made, while her father "
    "bargains with Lady Corvina for her life.",
    "Picks up from Episode 1 in the great hall.",
    [("INT. TOWER CELL – NIGHT", [
        (4.5, "Wide shot of a bare stone cell lit by one barred window.",
         [(0.5, 3.5, A, "Noor paces, rubbing the bruise on her cheek.")]),
        (4.0, "Medium shot as the door grinds open and a young servant slips in.",
         [(0.5, 3.0, "PIP (Nervous, Urgent)", "Miss Noor! I brought bread. And news.")]),
        (3.5, "Close-up of Noor grabbing the boy's sleeve.",
         [(0.3, 2.8, "NOOR (Desperate)", "Is the Earl alive?")]),
        (4.0, "Close-up of Pip, eyes darting to the door.",
         [(0.4, 3.2, "PIP (Whispering)", "Barely. But the bottle, miss. It has no maker's mark.")]),
        (3.5, "Extreme close-up of Noor's face as she realises.",
         [(0.3, 2.8, "NOOR (Stunned)", "Every glass I make carries my mark.")]),
        (4.0, "Medium two-shot; Noor kneels to the boy's height.",
         [(0.5, 3.2, "NOOR (Fierce)", "Then someone forged it. Find who sold that bottle.")]),
    ]),
     ("INT. LADY CORVINA'S CHAMBER – NIGHT", [
        (5.0, "Wide shot of a candlelit chamber; Tomas stands before Lady Corvina, hat in hand.",
         [(0.5, 3.5, "TOMAS (Pleading)", "Take my workshop. Take everything. Spare my daughter.")]),
        (4.0, "Close-up of Lady Corvina smiling coldly over her wine.",
         [(0.5, 3.0, "LADY CORVINA (Mocking)", "Your workshop is worth less than her rope.")]),
        (4.0, "Medium shot of Tomas falling to his knees.",
         [(0.5, 3.2, "TOMAS (Broken)", "Then take me instead. I am the glassblower.")]),
        (4.5, "Close-up as Lady Corvina leans down, almost tender.",
         [(0.5, 3.6, "LADY CORVINA (Sinister)", "How noble. But I don't want you, old man. I want her silence.")]),
        (4.0, "Over-the-shoulder shot: the masked witness waits in the shadows behind the curtain.",
         [(0.5, 3.0, A, "The silver mask catches the candlelight.")]),
        (3.5, "Close-up of Lady Corvina's eyes flicking to the curtain.",
         [(0.3, 2.8, "LADY CORVINA (Cold)", "Make sure she never testifies.")]),
        (3.0, "Black screen.",
         [(0.2, 2.6, S, "A low ominous drone. Cut to black.")]),
    ])])

EP3 = episode(3,
    "At the trial, Noor proves the poisoned bottle was never hers, but the masked witness unmasks and the "
    "court gasps: it is Noor's sister, Lena, believed dead for five years.",
    "Picks up the morning after Episode 2.",
    [("INT. COURTROOM – DAY", [
        (5.0, "Wide shot of a packed courtroom; Noor in chains at the dock.",
         [(0.5, 4.0, A, "The crowd jeers as Noor is led in.")]),
        (4.0, "Medium shot of the old Judge striking his gavel.",
         [(0.2, 0.8, S, "The gavel bangs."),
          (1.0, 2.8, "JUDGE MARLOW (Stern)", "The accused will answer the charge.")]),
        (4.0, "Close-up of Noor holding up her hand, palm open.",
         [(0.5, 3.2, "NOOR (Resolute)", "Bring me any glass from my workshop. And the poison bottle.")]),
        (4.5, "Insert: two bottles side by side on the judge's table.",
         [(0.5, 3.5, A, "Pip places the bottles down, hands shaking.")]),
        (4.0, "Close-up of Noor turning one bottle to the light.",
         [(0.4, 3.4, "NOOR (Firm)", "Mine has a tiny swallow in the base. The poison bottle has nothing.")]),
        (3.5, "Wide shot as murmurs sweep through the courtroom.",
         [(0.3, 2.8, S, "The crowd erupts in shocked murmurs.")]),
        (4.0, "Medium shot of Lady Corvina rising, furious.",
         [(0.4, 3.2, "LADY CORVINA (Furious)", "A swallow proves nothing! The witness saw her!")]),
        (4.0, "Medium shot of the masked witness stepping into the aisle.",
         [(0.5, 3.0, "MASKED WITNESS (Cold)", "Then let the court see my face.")]),
        (3.5, "Extreme close-up of gloved fingers untying the silver mask.",
         [(0.3, 2.8, A, "The mask falls and clatters on the floor.")]),
        (3.5, "Close-up of a young woman's scarred face, identical eyes to Noor's.",
         [(0.3, 2.4, S, "A collective gasp.")]),
        (4.0, "Extreme close-up of Noor, all colour gone from her face.",
         [(0.4, 3.0, "NOOR (Shocked, Trembling)", "Lena? You died in the fire.")]),
        (4.0, "Close-up of Lena smiling without warmth.",
         [(0.5, 3.0, "LENA (Venomous)", "You left me in that fire, sister.")]),
        (3.0, "Black screen.",
         [(0.2, 2.6, S, "A cliffhanger sting slams. Cut to black.")]),
    ])])

EP4 = episode(4,
    "Lena tells the court how the fire really started, Tomas confesses a secret he kept for five years, and "
    "Lady Corvina's hold on the court begins to crack.",
    "Picks up immediately after the unmasking in Episode 3.",
    [("INT. COURTROOM – CONTINUOUS", [
        (4.0, "Medium shot of Lena walking slowly toward the dock.",
         [(0.5, 3.0, "LENA (Bitter)", "Five years I lived with these scars.")]),
        (4.0, "Close-up of Noor shaking her head.",
         [(0.4, 3.2, "NOOR (Desperate)", "I tried to reach you. The roof came down!")]),
        (4.5, "Wide shot as Tomas pushes through the crowd to the front.",
         [(0.5, 3.5, "TOMAS (Anguished)", "Stop! It was not Noor. It was me.")]),
        (4.0, "Close-up of Lena turning, stunned.",
         [(0.4, 3.0, "LENA (Stunned)", "Papa?")]),
        (5.0, "Medium shot of Tomas, tears on his face.",
         [(0.5, 4.2, "TOMAS (Broken)", "Lady Corvina paid me to fire the old workshop. I did not know you were inside.")]),
        (3.5, "Close-up of Lady Corvina's face freezing.",
         [(0.3, 2.8, A, "Her wine cup slips and shatters.")]),
        (4.0, "Medium shot of Judge Marlow leaning forward.",
         [(0.5, 3.0, "JUDGE MARLOW (Grave)", "Lady Corvina. Is this true?")]),
        (4.0, "Close-up of Lady Corvina, recovering her smile.",
         [(0.5, 3.2, "LADY CORVINA (Smooth)", "The words of a drunk old man.")]),
        (4.5, "Wide shot as Pip runs in, waving a ledger.",
         [(0.5, 3.5, "PIP (Shouting)", "The bottle seller's ledger! Her steward bought it!")]),
        (4.0, "Close-up of Lady Corvina's eyes narrowing at Lena.",
         [(0.4, 3.2, "LADY CORVINA (Threatening)", "Choose your next words carefully, girl.")]),
        (4.0, "Two-shot of Lena and Noor, face to face.",
         [(0.5, 3.0, "LENA (Torn)", "If I tell the truth, she kills us both.")]),
        (3.0, "Black screen.",
         [(0.2, 2.6, S, "An ominous drone swells. Cut to black.")]),
    ])])

if __name__ == "__main__":
    here = Path(__file__).parent
    for n, text in enumerate((EP1, EP2, EP3, EP4), 1):
        (here / f"episode-00{n}-The Glass Heir.txt").write_text(text, encoding="utf-8")
    print("wrote 4 episodes to", here)
