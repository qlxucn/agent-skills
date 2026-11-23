---
name: transcript
description: Transcribe audio or video recordings (meetings, Zoom / Teams / 腾讯会议 / 飞书 recordings, screen recordings, KT/handover sessions, interviews, calls, voice memos, lectures, podcasts; m4a, mp3, wav, mp4, mov, mkv, webm, ...) into a speaker-labeled Markdown transcript with a summary, entirely on this machine - faster-whisper for speech-to-text, pyannote for who-spoke-when, memory-capped at 10 GB so the Mac stays usable. Use this whenever the user wants a recording transcribed, asks for 转写 / 转录 / 逐字稿 / 会议纪要 / 视频转文字 from an audio or video file, wants speaker labels or "who said what", or wants notes or a summary of a recording - in any language, even if they never say "transcript".
---

# Transcript

Turns an audio or video recording into `<YYYY-MM-DD>-<english-topic>.md` next to the recording: a header, a summary, then the full timestamped transcript with speaker labels.

The heavy, deterministic work (decoding, speech-to-text, diarization, merging, rendering) lives in `scripts/`. Your part is the judgment the scripts can't make: fixing misheard terms, naming the topic, working out who the speakers are, writing the summary, and confirming the speakers with the user.

## Ground rules, and why

- **Stay local.** Recordings often contain credentials, customer data and internal details. Don't send audio or transcript text to cloud services unless the user asks for that.
- **Protect the machine.** Stages run one at a time in separate processes, each watched by a guard that aborts it above `--max-mem-gb` (default 10). The guard counts Apple-GPU memory too, which plain RSS misses. Speech-to-text (CPU) peaks at roughly 2.5–5 GB; diarization (Apple GPU) at about 5 GB. Never run two transcriptions at once: that's what would actually exhaust memory.
- **Offline once set up.** After the first run has downloaded the models, the scripts run with `HF_HUB_OFFLINE=1` and pyannote's usage telemetry turned off, so nothing leaves the machine.
- **Don't invent content.** The summary and the speaker names must come from what was said. A visible recognition error is better than a confident wrong "fix". Refer to people by name or role, not by guessed pronouns: a voice doesn't tell you someone's gender.

`<skill-dir>` below is the directory containing this file.

## 1. Setup

```bash
bash <skill-dir>/scripts/setup.sh
```

The first run creates an isolated Python env (`~/.local/share/transcript-skill/venv`, ~1.2 GB) and verifies access to the pyannote model. Later runs take seconds. It ends with `PYTHON=<path>`: use that interpreter for every script below.

If it reports a missing Hugging Face token or missing model access, pass its instructions on to the user and stop until they have done them. pyannote's model is free but gated, and diarization can't run without access.

## 2. Transcribe and diarize

```bash
$PYTHON <skill-dir>/scripts/transcribe.py run "<audio or video file>" [--language zh] [--num-speakers N]
```

- `--language`: pass it when the user says the language or it's obvious; otherwise omit it to auto-detect. For `zh` the script biases Whisper toward simplified characters.
- `--num-speakers`: pass only a count the user actually gave you. A wrong fixed count does more harm than auto-detection.
- **Video files** (mp4, mov, mkv, webm, ...): pass the video itself and don't extract the audio first. The script decodes only the first audio track, never the picture, so it costs the same as an audio file. The output then sits next to the video, and the date comes from the video's metadata.
  - Only speech is transcribed. Anything shown on screen but not said aloud (slides, shared code, chat messages) isn't in the transcript, so the summary can't describe it.
  - `No audio track in ...`: for example, a screen recording made with the microphone off. Tell the user; there's nothing to transcribe.
  - `note: N audio tracks; transcribing track 1 only`: some recorders put the microphone and the computer audio on separate tracks. Mention this in the report. If the user wants another track, or all tracks mixed, make an audio file next to the video and transcribe that instead. `touch -r` keeps the video's date, which ffmpeg doesn't copy:
    ```bash
    ffmpeg -i in.mkv -map 0:a:1 -c copy in-track2.mka && touch -r in.mkv in-track2.mka               # second track
    ffmpeg -i in.mkv -filter_complex amix=inputs=2 -vn in-mixed.m4a && touch -r in.mkv in-mixed.m4a  # two tracks mixed
    ```
- **How long it takes** (M1 Pro): an 82-minute recording took 9 min for speech-to-text and 5 min for diarization on the Apple GPU. Allow more if the machine is busy. For anything over a couple of minutes, run it in the background, tell the user roughly how long it will take, and wait for the completion notification instead of polling. The log prints progress and memory every 5 minutes of audio.
- The last line is `WORK_DIR=<dir>`. Every intermediate file lives there (default `~/.cache/transcript-skill/<name>-<hash>/`).
- The memory cap was hit if you see `ABORT: ... used X GB` (exit 3) or `MPS backend out of memory ... max allowed`. Report it; don't raise `--max-mem-gb` without asking.
- Reruns are cheap. Finished stages are cached, so a rerun with a different `--num-speakers` redoes only diarization.

## 3. Read the transcript

```bash
$PYTHON <skill-dir>/scripts/render.py draft $WORK_DIR      # writes $WORK_DIR/draft.txt: "[hh:mm:ss] A: text" paragraphs
$PYTHON <skill-dir>/scripts/render.py speakers $WORK_DIR   # talk time, segment count, sample lines per speaker
$PYTHON <skill-dir>/scripts/render.py terms $WORK_DIR      # non-English recordings only: Latin-script words by frequency
```

Read `info.json`, the `speakers` output and all of `draft.txt`. For long recordings, read the draft in chunks of about 300 lines and keep running notes as you go, because the summary has to cover the whole recording, not just the start. While reading, collect four things:

**a. Replacements (misheard terms).** Whisper reliably mangles product names, English technical terms in non-English speech, and homophones. Typical examples in Chinese speech: 钉钉 → 丁丁 / 滴滴; 告警 → 告紧; Nacos → Nuckles / Nucos / Narcos; Docker Compose → composer / Compersor; Jenkins → Jankins. The `terms` list puts the several spellings of one English word side by side. Homophones in Chinese (or any non-Latin script) only show up when you read the draft, so read it with that in mind. Only add a replacement when the context makes the intended word clear. Prefer a specific string (`滴滴机器人` → `钉钉机器人`) over a broad one that could hit legitimate uses (`滴滴`). Leave genuinely ambiguous words as they are and list them in the report.

**b. Who the speakers are.** Give a speaker a name or role only when there's evidence. Good evidence: being addressed by name (if B says "张总，您看呢？", then the person B is talking to, usually the previous or next speaker, is 张总), introducing themselves, or a clear role, such as the person explaining a system versus the person asking about it. A role alone is a fine label (`接收方`, `Backend lead`). Without evidence, keep the default label (`说话人 A` / `Speaker A`). Note your evidence, because you'll show it to the user in step 6. Names come through speech recognition, so they can be misspelled: an unusual spelling, or one name written two ways, is a sign. Keep the name as heard unless the context makes the right form clear (a title like 王公 → 王工, or the name said more clearly elsewhere). In that case fix it with a replacement, and still raise the doubt in step 6, where the user settles it.

Watch for two kinds of diarization error:
- **One person split in two.** One id says only a few short lines that sound like another speaker. Point it out in step 6 instead of silently merging the two.
- **A short line credited to the wrong person.** Speaker detection often mislabels a one- or two-second reply ("sure", "I'll handle it") that comes right after someone else's turn, and the draft then hides it inside that person's paragraph. When the content shows a line belongs to someone else (an answer to a question put to another person, or a later recap that names a different owner), look it up in `segments.json`, which has one entry per Whisper segment (usually a sentence or clause), each with its own speaker. Then move it with `reassign` in step 4. `reassign` moves a whole segment, so if the reply shares a segment with someone else's words it can't be split; flag it in step 6 instead.

**c. Title and slug.** The title is in the recording's language. The slug is an English, lowercase-hyphenated name of 3–6 words, specific enough to find later: `order-service-migration-review` or `q3-hiring-plan`, not `meeting-notes`. The renderer prefixes the recording date from the file's metadata.

**d. Summary material.** Topics, decisions, action items (who / what / when), and open questions. When you cite a timestamp, use one that starts a `draft.txt` line. The final file uses the same paragraphs, so the reader can find every cited time in the transcript.

## 4. Write `meta.json` and `summary.md` into `$WORK_DIR`

```json
{
  "title": "订单服务迁移评审",
  "slug": "order-service-migration-review",
  "speakers": {"A": "李工（架构师）", "B": "说话人 B"},
  "reassign": {"00:12:41": "B"},
  "replacements": [["滴滴机器人", "钉钉机器人"], ["Nucos", "Nacos"]]
}
```

- `speakers` maps the speaker ids (A, B, ...) to display names. Map two ids to the same name to merge them.
- `replacements` are plain substring replacements on each paragraph's text, applied in order.
- `reassign` moves the single sentence that starts at that second (`hh:mm:ss` of its `start` in `segments.json`) to another speaker id. It's optional.
- `out_dir` is optional: add it to write somewhere other than the recording's folder.

Once `meta.json` exists, `draft` and `speakers` apply its reassignments and replacements as well. Run `draft` again after adding a `reassign`, because paragraph boundaries move and summary timestamps should come from the new draft.

Write `summary.md` in the recording's language. Use `###` headings, because it's inserted under the document's own summary heading. Leave out any section that would be empty instead of padding it. Refer to people by name or role (not "he" / "she"), and keep relative dates as spoken ("by Thursday", "下周三"): converting them to calendar dates is guesswork.

```markdown
### 概要
2–4 句：这是什么会议、谁参与、最重要的结果。

### 主要议题
- **[00:03:10] 数据库迁移方案** — 1–2 句说明。

### 结论与决定
- …

### 待办事项
- [ ] 负责人 — 事项（截止时间，如有提到）[00:12:30]

### 待确认问题
- 会上没说清楚、需要后续确认的点。
```

For English recordings, use: Overview / Topics / Decisions / Action items / Open questions.

## 5. Render

```bash
$PYTHON <skill-dir>/scripts/render.py final $WORK_DIR   # prints the output path
```

Re-rendering overwrites the file the skill generated earlier. A file of the same name that the skill didn't create makes the renderer stop rather than overwrite it; pick another slug or `out_dir`.

## 6. Confirm the speakers with the user

Do this every time. Diarization sometimes splits one person into two or merges two people, and inferred names can be wrong. The user is the only one who knows. Run `render.py speakers $WORK_DIR` after the final render, so talk times and samples reflect your reassignments and replacements. Then list every speaker with their current label, your evidence, talk time, and two or three sample lines:

```
I found 2 speakers. Please confirm or correct:

A → 李工（架构师）: talk time 00:31:20, 290 segments. Presents the migration plan; addressed as 李工 at [00:00:15].
  - [00:02:41] 这次迁移我们分两步走，先切读流量，再切写流量。
  - [00:18:05] …
B → 说话人 B: talk time 00:09:45, 88 segments. Asks about rollback and timelines; no name mentioned.
  - [00:00:15] 李工，那回滚方案是怎么考虑的？

Reply with e.g. "B is Alice", "A and C are the same person", or "there were 3 people".
```

Then apply the answer:
- **Rename:** edit `speakers` in `meta.json` and re-render.
- **Same person:** map both ids to one name and re-render.
- **A single line was someone else** ("the line at 00:12:41 was Alice"): add it to `reassign` and re-render.
- **Wrong number of people:** rerun `transcribe.py run` with `--num-speakers N`. Only diarization reruns, which takes minutes. Then re-check `speakers` and the draft, because ids can change, update `meta.json`, re-render, and confirm again.
- If the answer changes the topic or slug, delete the old output file you created so no stale copy is left behind.

If you can't ask the user (non-interactive run), give the step 7 report first and end with this confirmation message, noting that the labels are unconfirmed.

## 7. Report

Tell the user:
- the output path
- the duration
- the final speaker names
- peak memory per stage (from `info.json`)
- any terms you deliberately left uncorrected

If the transcript contains secrets (passwords, tokens, keys, internal hosts), say so: people tend to share meeting notes widely.
