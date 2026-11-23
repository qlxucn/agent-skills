#!/usr/bin/env python3
"""Local speech-to-text + speaker diarization with a memory cap.

  transcribe.py check                  verify ffmpeg + access to the pyannote model (seconds)
  transcribe.py run FILE [options]     full pipeline on an audio or video file; prints WORK_DIR=... at the end

`run` executes each heavy stage in its own child process, one after the other, so a
stage's memory is fully returned to the OS before the next one starts (this also keeps
PyAV and torchcodec, which bundle clashing ffmpeg libraries, out of the same process).
Stage results are cached in the work dir: rerunning with another --num-speakers only
redoes diarization.

Work dir contents:
  asr.json               faster-whisper segments [{start, end, text}]
  diarization-<n>.json   pyannote turns [{start, end, speaker}]  (n = speaker count or "auto")
  segments.json          ASR segments with a speaker id (A, B, ...) by largest time overlap
  info.json              source, recording date, duration, language, peak memory per stage
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# pyannote >= 4 sends usage telemetry (model, duration, speaker count) to otel.pyannote.ai unless disabled.
os.environ["PYANNOTE_METRICS_ENABLED"] = "false"

SR = 16000
WHISPER_MODEL = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
DIARIZATION_MODEL = "pyannote/speaker-diarization-community-1"
# Everything the two models load; once all are cached, runs need no network at all.
MODEL_FILES = {
    WHISPER_MODEL: ["config.json", "model.bin", "tokenizer.json", "vocabulary.json", "preprocessor_config.json"],
    DIARIZATION_MODEL: ["config.yaml", "segmentation/pytorch_model.bin", "embedding/pytorch_model.bin",
                        "plda/plda.npz", "plda/xvec_transform.npz"],
}
# Biases Whisper towards simplified characters; without it zh output is sometimes traditional.
ZH_PROMPT = "以下是普通话的句子，使用简体中文。"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def hms(t):
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def write_json(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def start_memory_guard(limit_gb, stage, extra=None):
    """macOS does not enforce RLIMIT_AS, so poll our own memory and hard-exit past the limit.

    extra: callable returning bytes held outside RSS (Apple-GPU / MPS allocations).
    """
    import psutil

    proc, limit, peak = psutil.Process(), limit_gb * 1024**3, [0]

    def watch():
        while True:
            rss = proc.memory_info().rss + (extra() if extra else 0)
            peak[0] = max(peak[0], rss)
            if rss > limit:
                sys.stderr.write(f"\nABORT: {stage} used {rss / 1024**3:.1f} GB > --max-mem-gb {limit_gb}\n")
                sys.stderr.flush()
                os._exit(3)
            time.sleep(0.5)

    threading.Thread(target=watch, daemon=True).start()
    return lambda: round(peak[0] / 1024**3, 2)


def audio_tracks(path):
    """Number of audio streams: a video can have none (screen recording without mic) or several."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.exit(f"ffprobe could not read {path}:\n{r.stderr[-800:]}")
    return len(r.stdout.split())


def load_audio(path):
    """Decode the first audio track of any ffmpeg-readable audio or video file to 16 kHz mono float32
    (~230 MB per hour). Video frames are never decoded."""
    import numpy as np

    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0",
         "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True,
    )
    if r.returncode != 0:
        sys.exit(f"ffmpeg could not decode {path}:\n{r.stderr.decode(errors='replace')[-800:]}")
    audio = np.frombuffer(r.stdout, np.float32).copy()
    if audio.size == 0:
        sys.exit(f"No audio stream decoded from {path}")
    return audio


def recorded_at(path):
    """Container creation_time tag (set by phones, Voice Memos, cameras) in local time, else file mtime."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=creation_time", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    tag = r.stdout.strip()
    if tag:
        when = datetime.fromisoformat(tag.replace("Z", "+00:00")).astimezone()
        if when.year >= 2000:  # some video tools write a zero timestamp (1904 or 1970) instead of none
            return when
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone()


def models_cached():
    from huggingface_hub import try_to_load_from_cache

    return all(isinstance(try_to_load_from_cache(repo, f), str) for repo, files in MODEL_FILES.items() for f in files)


def check_access():
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"{tool} not found. Install it with: brew install ffmpeg")
    if models_cached():
        return
    from huggingface_hub import get_token, hf_hub_download
    from huggingface_hub.errors import RepositoryNotFoundError

    try:
        hf_hub_download(DIARIZATION_MODEL, "config.yaml")
    except RepositoryNotFoundError:  # also raised (as GatedRepoError) for gated repos without access
        url = f"https://huggingface.co/{DIARIZATION_MODEL}"
        if get_token():
            sys.exit(f"Hugging Face token found, but it has no access to {DIARIZATION_MODEL}.\n"
                     f"Open {url} while logged in and accept the conditions, then retry.")
        sys.exit("No Hugging Face token found. pyannote's model is free but gated:\n"
                 "  1. Create a read token: https://huggingface.co/settings/tokens\n"
                 f"  2. Accept the conditions: {url}\n"
                 "  3. Run: uvx --from huggingface_hub hf auth login   (or export HF_TOKEN=...)")


# ---------------------------------------------------------------- stages (child processes)

def stage_asr(audio_path, out, language, threads, max_mem_gb):
    peak = start_memory_guard(max_mem_gb, "asr")
    t0 = time.time()
    from faster_whisper import WhisperModel

    audio = load_audio(audio_path)
    # int8 on CPU: ~1.5 GB of weights; Apple GPUs are not supported by CTranslate2 anyway.
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=threads, num_workers=1)
    if language is None:
        language, prob, _ = model.detect_language(audio, vad_filter=True, language_detection_segments=3)
        log(f"asr: detected language '{language}' (p={prob:.2f})")
    segments, info = model.transcribe(
        audio,
        language=language,
        vad_filter=True,                    # skip silence; avoids hallucinated text in pauses
        condition_on_previous_text=False,   # prevents repetition loops on long recordings
        initial_prompt=ZH_PROMPT if language == "zh" else None,
    )
    rows, next_log = [], 300
    for s in segments:
        rows.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        if s.end >= next_log:
            log(f"asr: {hms(s.end)} / {hms(info.duration)}  mem {peak()} GB")
            next_log += 300
    write_json(out, {"language": language, "duration_seconds": round(info.duration), "segments": rows,
                     "peak_mem_gb": peak(), "elapsed_s": round(time.time() - t0)})
    log(f"asr: done, {len(rows)} segments, peak {peak()} GB")


def stage_diarize(audio_path, out, num_speakers, threads, max_mem_gb):
    t0 = time.time()
    import warnings

    import torch
    from pyannote.audio import Pipeline

    warnings.filterwarnings("ignore", message=r"std\(\): degrees of freedom")  # harmless, floods the log
    # The Apple GPU is ~6x faster than CPU here with identical output. Its memory is not part of RSS,
    # so the guard adds it, and the per-process fraction makes MPS itself refuse to grow past the cap.
    mps = torch.backends.mps.is_available()
    peak = start_memory_guard(max_mem_gb, "diarize", extra=torch.mps.driver_allocated_memory if mps else None)
    torch.set_num_threads(threads)
    pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL)  # token from `hf auth login` or HF_TOKEN
    if pipeline is None:
        sys.exit(f"Could not load {DIARIZATION_MODEL}; run `transcribe.py check`")
    if mps:
        torch.mps.set_per_process_memory_fraction(min(1.0, max_mem_gb * 1024**3 / torch.mps.recommended_max_memory()))
        pipeline.to(torch.device("mps"))
    log(f"diarize: device {'mps' if mps else 'cpu'}")
    waveform = torch.from_numpy(load_audio(audio_path))[None]
    state = {"step": None, "pct": -1}

    def hook(step, artifact, file=None, total=None, completed=None):
        if step != state["step"]:
            state.update(step=step, pct=-1)
            log(f"diarize: {step}")
        if total and completed is not None:
            pct = min(100, completed * 100 // total // 20 * 20)
            if pct > state["pct"]:
                state["pct"] = pct
                log(f"diarize: {step} {pct}%  mem {peak()} GB")

    result = pipeline({"waveform": waveform, "sample_rate": SR}, num_speakers=num_speakers, hook=hook)
    # exclusive_* has no overlapping turns, which is what we need to give each sentence one speaker.
    turns = [{"start": round(t.start, 2), "end": round(t.end, 2), "speaker": spk}
             for t, _, spk in result.exclusive_speaker_diarization.itertracks(yield_label=True)]
    write_json(out, {"turns": turns, "device": "mps" if mps else "cpu",
                     "peak_mem_gb": peak(), "elapsed_s": round(time.time() - t0)})
    log(f"diarize: done, {len(turns)} turns, {len({t['speaker'] for t in turns})} speakers, peak {peak()} GB")


# ---------------------------------------------------------------- merge (pure functions)

def assign_speakers(segments, turns):
    """Give each ASR segment the speaker who talks most during it. Turns must not overlap."""
    turns = sorted(turns, key=lambda t: t["start"])
    out, i = [], 0
    for seg in segments:
        while i < len(turns) and turns[i]["end"] <= seg["start"]:
            i += 1
        talk, j = {}, i
        while j < len(turns) and turns[j]["start"] < seg["end"]:
            o = min(seg["end"], turns[j]["end"]) - max(seg["start"], turns[j]["start"])
            talk[turns[j]["speaker"]] = talk.get(turns[j]["speaker"], 0) + o
            j += 1
        if talk:
            spk = max(talk, key=talk.get)
        else:  # segment sits in a gap between turns: take the closest neighbour
            near = turns[max(i - 1, 0): i + 1]
            spk = min(near, key=lambda t: max(t["start"] - seg["end"], seg["start"] - t["end"]))["speaker"]
        out.append({**seg, "speaker": spk})
    return out


def relabel(segments):
    """SPEAKER_03 -> A, B, C ... in order of first appearance."""
    ids = {}
    for s in segments:
        ids.setdefault(s["speaker"], chr(ord("A") + len(ids)))
    return [{**s, "speaker": ids[s["speaker"]]} for s in segments]


# ---------------------------------------------------------------- orchestration

def default_work_dir(audio):
    st = audio.stat()
    key = hashlib.sha1(f"{audio}|{st.st_size}|{st.st_mtime}".encode()).hexdigest()[:8]
    return Path.home() / ".cache" / "transcript-skill" / f"{audio.stem}-{key}"


def run_stage(name, *args):
    rc = subprocess.run([sys.executable, __file__, "_stage", name, *map(str, args)]).returncode
    if rc != 0:
        sys.exit(f"{name} stage failed (exit {rc}); see the messages above")


def cmd_run(a):
    audio = Path(a.audio).expanduser().resolve()
    if not audio.is_file():
        sys.exit(f"Not a file: {audio}")
    check_access()  # fail before the long ASR stage, not after it
    tracks = audio_tracks(audio)
    if tracks == 0:
        sys.exit(f"No audio track in {audio.name}: nothing to transcribe")
    if tracks > 1:
        log(f"note: {tracks} audio tracks; transcribing track 1 only")
    if models_cached():
        os.environ["HF_HUB_OFFLINE"] = "1"  # inherited by the stages: no network access at all
        log("models cached: running offline")
    work =Path(a.work_dir).expanduser().resolve() if a.work_dir else default_work_dir(audio)
    work.mkdir(parents=True, exist_ok=True)
    os.nice(10)  # inherited by the stage processes: keep the Mac responsive
    log(f"work dir: {work}")

    asr_path = work / "asr.json"
    if asr_path.exists():
        cached = read_json(asr_path)["language"]
        if a.language and a.language != cached:
            sys.exit(f"Cached asr.json is in '{cached}', not '{a.language}'. Delete {asr_path} to redo ASR.")
        log("asr: cached")
    else:
        run_stage("asr", audio, asr_path, a.language or "auto", a.threads, a.max_mem_gb)

    diar_path = work / f"diarization-{a.num_speakers or 'auto'}.json"
    if diar_path.exists():
        log("diarize: cached")
    else:
        run_stage("diarize", audio, diar_path, a.num_speakers or 0, a.threads, a.max_mem_gb)

    asr, diar = read_json(asr_path), read_json(diar_path)
    if not asr["segments"]:
        sys.exit("ASR produced no text (silent or unsupported audio?)")
    if not diar["turns"]:
        sys.exit("Diarization found no speech turns")
    segments = relabel(assign_speakers(asr["segments"], diar["turns"]))
    when = recorded_at(audio)
    write_json(work / "segments.json", segments)
    write_json(work / "info.json", {
        "source": str(audio),
        "recorded_at": when.isoformat(timespec="seconds"),
        "date": when.strftime("%Y-%m-%d"),
        "duration_seconds": asr["duration_seconds"],
        "language": asr["language"],
        "num_speakers_requested": a.num_speakers,
        "models": {"asr": WHISPER_MODEL, "diarization": DIARIZATION_MODEL},
        "peak_mem_gb": {"asr": asr["peak_mem_gb"], "diarize": diar["peak_mem_gb"]},
        "elapsed_s": {"asr": asr["elapsed_s"], "diarize": diar["elapsed_s"]},
    })
    talk = {}
    for s in segments:
        talk[s["speaker"]] = talk.get(s["speaker"], 0) + s["end"] - s["start"]
    log(f"done: {len(segments)} segments; talk time " + ", ".join(f"{k} {hms(v)}" for k, v in talk.items()))
    print(f"WORK_DIR={work}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="verify ffmpeg and pyannote model access")
    r = sub.add_parser("run", help="transcribe + diarize an audio/video file")
    r.add_argument("audio", help="audio or video file (only its first audio track is used)")
    r.add_argument("--language", help="ISO code, e.g. zh, en (default: auto-detect)")
    r.add_argument("--num-speakers", type=int, help="exact speaker count, if known (improves diarization)")
    r.add_argument("--max-mem-gb", type=float, default=10, help="abort a stage above this RSS (default 10)")
    r.add_argument("--threads", type=int, default=max(1, min(6, (os.cpu_count() or 4) - 2)))
    r.add_argument("--work-dir", help="default: ~/.cache/transcript-skill/<name>-<hash>")
    s = sub.add_parser("_stage")  # internal: one heavy stage in a fresh process
    s.add_argument("name", choices=["asr", "diarize"])
    s.add_argument("audio")
    s.add_argument("out", type=Path)
    s.add_argument("param")
    s.add_argument("threads", type=int)
    s.add_argument("max_mem_gb", type=float)
    a = p.parse_args()

    if a.cmd == "check":
        check_access()
        print("OK: ffmpeg found and pyannote model accessible")
    elif a.cmd == "run":
        cmd_run(a)
    elif a.name == "asr":
        stage_asr(a.audio, a.out, None if a.param == "auto" else a.param, a.threads, a.max_mem_gb)
    else:
        stage_diarize(a.audio, a.out, int(a.param) or None, a.threads, a.max_mem_gb)


if __name__ == "__main__":
    main()
