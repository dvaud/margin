"""Write Margin's built-in social practice theory codebooks (CSV + JSON sidecar), `practice` and `change_framing`.

    python tools/make_practice_codebooks.py            # into src/margin/data/codebooks
    python tools/make_practice_codebooks.py <folder>   # anywhere else

Columns: code, description, group, group_name, keywords, include, exclude, source (all read by Margin 0.9; see
margin/frameworks.py). Edit the codes here, not in the CSV files, and run the script again.
"""
import csv
import json
import sys
from pathlib import Path

COLS = ["code", "description", "group", "group_name", "keywords", "include", "exclude", "source"]

GROUPS = {
    "EL": "Elements of a practice",
    "PF": "Performing the practice (zooming in)",
    "KN": "Knowing and accounting",
    "RP": "Rules, resources and power",
    "DY": "Dynamics: links made, sustained and broken",
    "NX": "Connections between practices (zooming out)",
}

PRACTICE = [
    # --- elements
    ("EL1", "Materials: the things a practice is made with, such as objects, tools, devices, infrastructures, "
            "consumables and the body as physical equipment.",
     "equipment; kit; device; tool; machine; app; infrastructure; network; supplies; bought; broken; installed",
     "A thing takes part in doing the practice: it is used, needed, missing, failing or bought for it.",
     "Things mentioned only as the setting. When the thing takes over a skill or changes what the practice means, "
     "also code DY4. Who owns or controls it: RP3.",
     "Shove et al. 2012: 23; Spaargaren et al. 2016: 7-10"),
    ("EL2", "Competences: the know-how and understanding needed to do the practice and to judge whether it is done "
            "well, such as skills, techniques and learned procedures.",
     "know how; skill; learn; trained; training; knack; technique; experience; expertise; properly; certified",
     "Knowing how, lacking the skill, learning a technique, judging whether something is done well.",
     "Knowing what to do next without thinking about it: KN1. Being taught as a newcomer joining the practice: DY6.",
     "Shove et al. 2012: 23; Spaargaren et al. 2016: 7"),
    ("EL3", "Meanings: the shared social and symbolic significance of taking part in the practice, what doing it "
            "stands for, what it says about you and what it is associated with.",
     "seen as; stands for; image; status; normal; cool; embarrassing; old-fashioned; it's about; people like us",
     "A shared significance, image, idea or aspiration attached to doing the practice.",
     "One person's own reason for doing it: KN2. How it feels to do it: PF5. A change in what it is associated "
     "with: DY5.",
     "Shove et al. 2012: 23-24; Spaargaren et al. 2016: 7"),
    # --- performing
    ("PF1", "Sayings and doings: what people actually do and say to get the practice done, step by step, including "
            "methods, tricks of the trade and workarounds.",
     "first; then; what we actually do; step; check; fill in; ring; hand over; trick; the way I do it",
     "An account or observation of how the activity is accomplished, move by move.",
     "Why it is done: KN2. The rule saying how it should be done: RP1.",
     "Nicolini 2012: 53, 220-221"),
    ("PF2", "Bodies: how the practice is carried out through the body, such as posture, gesture, movement, strain "
            "and the trained or habituated body, and how the practice shapes bodies.",
     "hands; posture; movement; gesture; physically; tired; strain; feel; touch; body",
     "The body doing the practice, sensing, straining, or being shaped by it.",
     "How doing it feels emotionally: PF5. The body only as a limit on having or using things: EL1.",
     "Nicolini 2012: 220, 223; Shove et al. 2012: 23"),
    ("PF3", "Timing and sequence: when and in what order the practice is done, its rhythms, schedules, waiting and "
            "rush, and clashes between the rhythms of different practices.",
     "every morning; schedule; rota; shift; deadline; too early; too late; wait; rush; time slot; weekend",
     "When something is done, how often, in which order, or how timings fit or clash.",
     "Repetition that keeps the practice going: DY2 (code both when the passage is about routine timing).",
     "Nicolini 2012: 220, 222; Giddens 1984: 35"),
    ("PF4", "Practical concerns and ends: what matters to practitioners and what the practice is for, the shared "
            "sense of what needs to be done and of when it counts as done (teleo-affective structure).",
     "what matters; the point is; goal; aim; has to be done; a good job; priority; worry; purpose; done properly",
     "The ends, concerns and priorities practitioners share, or the standard of a job well done.",
     "One person's own motive or reason: KN2. A prescribed procedure: RP1.",
     "Nicolini 2012: 220, 224-225; Spaargaren et al. 2016: 7-8, 10"),
    ("PF5", "Emotions and experience: how doing the practice feels, such as fun, boredom, fear, pride, disgust or "
            "excitement, and emotions that draw people in or put them off.",
     "fun; enjoy; boring; scary; exciting; hate; love; stress; proud; nervous; buzz",
     "A feeling attached to doing the practice or to taking part in it.",
     "What doing it signifies to others: EL3.",
     "Spaargaren et al. 2016: 11-12, 19"),
    ("PF6", "Breakdown and improvisation: moments when the routine fails or is disrupted and people have to think, "
            "discuss, improvise or work around it, and tensions between how it should be done and how it is done.",
     "broke down; went wrong; power cut; suddenly; had to figure out; improvise; workaround; officially; in "
     "practice; back to normal",
     "A disruption and what practitioners do about it, or a gap between the official and the actual way.",
     "A lasting end to the practice: DY3. A rule as such: RP1.",
     "Spaargaren et al. 2016: 10, 18; Nicolini 2012: 48, 220, 225-226; Giddens 1984: 6"),
    # --- knowing
    ("KN1", "Practical consciousness: tacit knowing how to go on, what people do without deliberating or without "
            "being able to put it into words, such as habit, feel and second nature.",
     "just do it; without thinking; automatic; autopilot; habit; second nature; feel for it; hard to explain; "
     "obvious what to do",
     "Signs that the doing rests on tacit knowledge: not deliberating, not being able to say how.",
     "A skill described as learned: EL2. Repetition over time: DY2. In interviews everything is said aloud: code "
     "this only where the speaker marks the knowing as tacit.",
     "Giddens 1984: 4, 7; Spaargaren et al. 2016: 10; Nicolini 2012: 48"),
    ("KN2", "Accounts, reasons and motives: people's own explanations of why they do what they do, the reasons, "
            "aims and motives they give for their conduct.",
     "because; the reason; why I; I wanted; my aim; it makes sense; so that; otherwise; I decided",
     "The speaker accounts for their own conduct. Code the account as given, not an inner state behind it.",
     "Justification demanded by others, or rights and sanctions: RP2. Shared ends of the practice: PF4.",
     "Giddens 1984: 3-7; Nicolini 2012: 225"),
    # --- rules, resources, power
    ("RP1", "Rules: the procedures and norms of how the practice is done, written or unwritten, such as how it is "
            "done here, what counts as doing it right and what is not allowed.",
     "rule; supposed to; not allowed; procedure; protocol; standard; guideline; regulation; unwritten; how it's "
     "done here",
     "Procedural rules (how it is done) and moral rules (what is appropriate), tacit or formalised.",
     "Being called to justify or sanctioned: RP2. A plain habit is not a rule: DY2.",
     "Giddens 1984: 18-22; Nicolini 2012: 46; Spaargaren et al. 2016: 7-8"),
    ("RP2", "Accountability and legitimation: having to justify the practice or being held to account for it, "
            "rights and obligations, sanctions, approval and disapproval.",
     "justify; accountable; held responsible; duty; entitled; obligation; in trouble; sanction; approve; legitimate",
     "Normative grounds are invoked: who may, who must, what happens if not, what makes it legitimate.",
     "Reasons without normative grounds: KN2. The procedure itself: RP1.",
     "Giddens 1984: 30; Nicolini 2012: 220, 225-227"),
    ("RP3", "Resources and access: command over things (money, land, equipment: allocative resources) and over "
            "people (authority, organisation: authoritative resources), and unequal access to what a practice needs.",
     "budget; funding; afford; cost; access; land; ownership; who controls; in charge; only the rich; couldn't get",
     "Having, lacking, controlling or being denied what the practice needs.",
     "The thing as part of the doing: EL1. Positions and pushing back: RP4.",
     "Giddens 1984: 16, 33; Shove et al. 2012: 28"),
    ("RP4", "Positions and power: who is who in the practice and who can make a difference, such as roles, "
            "asymmetries, deciding and deferring, and how those in weaker positions push back.",
     "who decides; not my place; sign off; boss; manager; had no say; pushed back; resist; gatekeeper; hierarchy",
     "Positions the practice makes available, how they are negotiated, and influence from above or below.",
     "Access to resources as such: RP3.",
     "Nicolini 2012: 220-222; Giddens 1984: 14-16; Spaargaren et al. 2016: 10, 20"),
    # --- dynamics
    ("DY1", "Making links: elements coming together so that the practice becomes possible or starts, a new "
            "combination of things, skills and meanings, a practice emerging.",
     "started; took up; once we had; became possible; caught on; new way of; began to; tried out; introduced",
     "A practice or a new variant beginning. Also elements that exist but are not yet combined (proto-practice): "
     "then the direction is pulls apart.",
     "A practice that already runs and is kept going: DY2.",
     "Shove et al. 2012: 21, 24-25, 45"),
    ("DY2", "Sustaining and routine: the practice kept going by being done again and again in a similar way, "
            "routine, habit and repetition, what keeps it in place.",
     "every day; always; as usual; routine; habit; keep doing; the same way; regularly; still",
     "Repetition, continuity, and whatever is said to keep the practice in place.",
     "The tacit form of the knowledge: KN1. The timetable as such: PF3.",
     "Shove et al. 2012: 24; Nicolini 2012: 48, 228; Spaargaren et al. 2016: 9-10"),
    ("DY3", "Breaking links: a practice, or part of it, falling away, such as giving up, dropping out, being "
            "replaced or dying out, and elements left unused, dormant or forgotten.",
     "stopped; gave up; no longer; nobody does; replaced by; died out; forgotten; abandoned; switched to; used to",
     "Ending, abandonment, defection, replacement, or the fate of elements no longer linked.",
     "A temporary disruption the practice recovers from: PF6.",
     "Shove et al. 2012: 25, 34-35, 58-60; Spaargaren et al. 2016: 18"),
    ("DY4", "Mutual shaping and delegation: a change in one element changing the others, such as a new device "
            "making a skill unnecessary or changing what the practice means, and tasks handed from people to things.",
     "does it for you; automatic; no need to know; made it easier; changed what; designed so; the system does; "
     "took over",
     "One element reshaping another, or a capacity passing from people to things (or back).",
     "Things merely used: EL1.",
     "Shove et al. 2012: 30-32; Nicolini 2012: 224, 228"),
    ("DY5", "Circulation and re-classification: elements travelling between places and practices, such as things "
            "transported or imported, know-how codified and decoded, meanings re-associated or rebranded.",
     "imported; came over from; adopted from; manual; guidelines; instructions; rebranded; now associated with; "
     "no longer seen as; spread",
     "An element moving, being packaged for travel, unpacked locally, or classified anew.",
     "The meaning as it stands: EL3. A whole practice spreading: say which element moved, and code that too.",
     "Shove et al. 2012: 39, 46-57"),
    ("DY6", "Learning and careers: how newcomers are drawn in, taught and socialised into the practice, how "
            "practitioners' own careers carry and change it, recruitment and defection.",
     "when I started; newcomer; novice; taught; mentor; induction; old hands; joined; recruit; new generation",
     "Joining, being taught the ropes, stories told to novices, careers inside the practice.",
     "A skill as such: EL2.",
     "Nicolini 2012: 220, 227; Shove et al. 2012: 40, 62; Spaargaren et al. 2016: 18"),
    # --- connections
    ("NX1", "Links between practices: one practice enabling, constraining, clashing with or depending on another, "
            "or sharing an element (the same skill, thing or meaning) with it.",
     "depends on; together with; clashes with; conflicts with; same skills as; also used for; alongside; combined with",
     "Two or more practices named in relation to each other.",
     "Effects of a practice on others: NX4.",
     "Shove et al. 2012: 36; Nicolini 2012: 228, 230; Spaargaren et al. 2016: 13"),
    ("NX2", "Bundles, complexes and institutions: large phenomena described as sets of connected practices and "
            "material arrangements, such as organisations, sites, sectors, supply chains and lasting institutions.",
     "sector; supply chain; system; industry; institution; tradition; network; the hospital; the whole chain",
     "A large arrangement described through the practices and things that make it up.",
     "Explaining conduct by a system or level as such: the change_framing codebook (CF3).",
     "Spaargaren et al. 2016: 12-13; Giddens 1984: 17, 24; Nicolini 2012: 214, 238"),
    ("NX3", "Acting at a distance: links between local practice and distant places or people through rules, "
            "protocols, plans, reports, figures and standards, local work summarised for others far away or "
            "distant decisions brought into local work.",
     "head office; regulation; reporting; targets; indicators; protocol; national; policy; figures; monitoring",
     "A mediator connects the here and now to the then and there, in either direction.",
     "A local rule with no distant link: RP1.",
     "Nicolini 2012: 235-236; Giddens 1984: 28, 37"),
    ("NX4", "Effects and unintended consequences: what a practice does beyond itself, such as knock-on effects on "
            "other practices, roles and identities, and outcomes nobody intended.",
     "knock-on; side effect; backfired; never meant; ended up; as a result; out of the loop; unintended",
     "Consequences of a practice for others, or outcomes that nobody aimed at.",
     "A practice depending on another: NX1.",
     "Nicolini 2012: 232-234; Giddens 1984: 8-14"),
]

FRAMING = [
    ("CF1", "Practices: conduct or change explained by shared, routine ways of doing and the things, skills and "
            "meanings they combine.",
     "routine; habit; everyday practice; the way it is done; infrastructure; skills; norms; doing",
     "The text explains what people do through the practices they take part in.",
     "", "Spaargaren et al. 2016: 4-8; Shove et al. 2012: 22"),
    ("CF2", "Individual choice: conduct or change explained by individuals' attitudes, values, preferences, "
            "information or rational decisions, or by background variables such as income and education.",
     "attitude; awareness; behaviour; choice; decide; motivation; preference; inform; nudge; incentive; consumer",
     "The text treats conduct as the outcome of individual decisions, or aims to change it by changing minds.",
     "", "Spaargaren et al. 2016: 3-4, 10; Giddens 1984: 3, 26; Nicolini 2012: 52-53, 225"),
    ("CF3", "Structure or system: conduct or change explained by structures, functions, the needs of a system, "
            "constraints acting like forces, or levels (micro and macro; niche, regime and landscape).",
     "structure; system; regime; landscape; macro; level; forces; functional; constraints; the market",
     "The text explains conduct by something above or outside the activity it explains.",
     "", "Giddens 1984: 1, 12, 15; Spaargaren et al. 2016: 6, 12, 16; Nicolini 2012: 234, 239"),
    ("CF4", "Technology: change attributed to a technology, or to its spread, by itself.",
     "technology; innovation; roll-out; uptake; adoption; smart; digital; device; will reduce; will enable",
     "The text expects a technology to change conduct without saying how it enters what people do.",
     "", "Shove et al. 2012: 29-30; Spaargaren et al. 2016: 20; Nicolini 2012: 51"),
]

out = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path(__file__).resolve().parents[1] / "src" / "margin" / "data" / "codebooks"
out.mkdir(parents=True, exist_ok=True)


def write(name, rows, groups, meta):
    with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")  # the repository keeps LF line ends
        w.writerow(COLS)
        for code, desc, kw, inc, exc, src in rows:
            g = code[:2]
            w.writerow([code, desc, g, groups[g], kw, inc, exc, src])
    (out / f"{name}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


write("practice", PRACTICE, GROUPS, {
    "title": "Social practice theory (25 codes)",
    "label": "practice code",
    "directional": True,
    "direction_labels": {"helps": "holds together", "hinders": "pulls apart", "mixed": "both",
                         "not_stated": "not stated"},
    "practice_and_element": True,
    "direction_note": "Relative to the practice the passage is about: does what it describes make or renew the links "
                      "that hold the practice together, or break them? (Shove et al. 2012: 21, 36)",
    "sources": ["Giddens 1984, The Constitution of Society, ch. 1",
                "Nicolini 2012, Practice Theory, Work, and Organization, ch. 3.1 and ch. 9",
                "Shove, Pantzar and Watson 2012, The Dynamics of Social Practice, ch. 2-3",
                "Spaargaren, Lamers and Weenink 2016, Practice Theory and Research, ch. 1"],
    "stance": "Programmatic eclecticism (Nicolini 2012: 213): Shove and Schatzki for elements and materials, Giddens "
              "for knowing, rules and resources, Nicolini for zooming in and out. Sensitising concepts, not a "
              "formula (Nicolini 2012: 240).",
})
write("change_framing", FRAMING, {"CF": "How a text explains conduct or change"}, {
    "title": "Framings of conduct and change (4 codes)",
    "label": "framing",
    "directional": False,
    "one_main": True,
})
print(f"wrote {len(PRACTICE)} + {len(FRAMING)} codes to {out}")
