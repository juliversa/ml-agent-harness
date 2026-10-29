---
name: explainer-video
description: Make a short narrated explainer video (animated graphs and voice) about a competition, a result, a model or any idea. Use 24 h into every competition (WEEK0 item 16), when asked for a video, an explainer, a visual summary, or /explainer-video.
---
# explainer-video
Turn an idea into a 3–6 minute narrated video where every on-screen fact has a source.

Needs: `kit/video/engine.py` (matplotlib frames, Kokoro-82M voice on CPU, ffmpeg); example project `kit/video/template/`. One-time setup: `bash kit/video/setup_video.sh` (packages + voice model in `$KOKORO_DIR`, default `~/.cache/kokoro`).

## Steps
1. **Ask what it is for, then write the story.** List 5–7 points the viewer should leave with, in plain words, then the storyboard in `STORYBOARD.md`: one scene per point, 8–15 scenes, 3–6 minutes. Lead with the audience's question; cut the rest to one line.
2. **Write FACTS before drawing.** In `FACTS.md`, map every number, name and date on screen to its source (`file:line` or URL, re-fetched). Mark made-up pictures **toy** and show `toy_tag` on screen. Cut any number with no source.
3. **Make the project folder** `<comp>/video/<name>/` (or `videos/<name>/` for non-competition topics) by copying `kit/video/template/`; the folder name becomes the mp4 name. In `scenes*.py`, write one `@scene(name, captions)` per idea; each picture element appears on the caption that speaks about it (`c[k]`). In `spoken.py`, spell acronyms and numbers for the voice (`SAY`) and rewrite lines for the ear (`SPOKEN`).
4. **Look before rendering.** Run `python3 kit/video/engine.py <proj> info`, then `still <i> <t>…` at every caption start + 2 s, and open each PNG. Fix overlaps, clipped text, text over captions (captions own y < 1.2), more than one idea per frame, unexplained jargon.
5. **Voice, then render.** Run `tts` → `check` (fails if any caption has missing or stale audio; re-run `tts` after any caption edit) → `render [workers]` → `concat`. Scratch goes to `$VIDEO_OUT` (default `/tmp/video-<name>/`).
6. **Review in rounds, each with two fresh readers who look for different things.** Brief each on the strongest model (brief starts with skills/coding-discipline/SKILL.md pasted verbatim, plus an `Output:` line). Give them the stills, the captions and `FACTS.md`; every reviewer checks every on-screen claim against its source. Usual rounds: (1) the owner's eyes (a non-expert: what is unclear?) + a domain expert (is it true?); (2) a video designer (one idea per frame, readable, in sync) + a sceptic (are the comparisons fair, are the numbers honest?); (3) an acceptance test: the reviewer explains each of the owner's questions back from the video alone; any wrong or missing answer is a fix. After each round, fix, re-render only the changed scenes (`render 4 3,7`), `concat`, and log in `STORYBOARD.md` what the round changed.
7. **Deliver** the mp4 file (never a public link) with its length and a 3-line summary. mp4/wav are git-ignored; commit the scripts, `FACTS.md` and `spoken.py`.

## Style
- Keep one colour per concept for the whole video (ours vs others, truth vs labels); say it once, keep it.
- Show the mechanism with a toy picture first, then the real numbers.
- Keep captions short (≤ 2 lines, ~15 words); the voice says the same thing, with numbers spoken ("point nine five four").
- Explain models by what they look at and how big, not by architecture names alone.
- Open with the viewer's question; just before the next steps, answer it in one line.
- Follow one real example through the whole video, with the same data in every scene; a second version of it contradicts the first.
- Pick real example data by a rule ("most typical spectrum", not the first hit); write the rule in `FACTS.md`.
- Compare like with like: offline and leaderboard numbers from the same model.
- Arithmetic on screen must hold exactly as written (139.04 − 1.01 = 138.03, not 139 − 1 = 138.03).
- Define each term on the slide where it first appears; mark guesses as guesses on screen ("rough", "forum guess").
- Draw labels on a background where lines cross them.
- End with what to do next, numbered, with why each step is in its place.

## Done when
The mp4 is delivered with its length and a 3-line summary, every review round's points are fixed, and the scripts, `STORYBOARD.md`, `FACTS.md` and `spoken.py` are committed.
