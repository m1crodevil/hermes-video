#!/usr/bin/env python3
"""/watch entry point: download video, extract frames, parse transcript.

Prints a markdown report to stdout listing frame paths + transcript. Claude
then Reads each frame path to see the video.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from config import DEFAULT_MIN_MOMENTS, frame_cap, get_config  # noqa: E402
from download import download, fetch_captions, is_url  # noqa: E402
from frames import MAX_FPS, auto_fps, auto_fps_focus, extract_at_timestamps, extract_keyframes, extract_scene_or_uniform, extract_two_pass, format_time, get_metadata, merge_frames, parse_time, parse_timestamps  # noqa: E402
from models import build_report  # noqa: E402
from transcribe import filter_range, format_transcript, parse_json3, parse_vtt  # noqa: E402
from whisper import load_api_key, transcribe_video  # noqa: E402
from transcript_moments import generate_prompt, format_transcript_for_analysis  # noqa: E402
from stats_collector import StatsTimer, collect_stats, format_stats_telegram, format_stats_compact  # noqa: E402


def _cleanup_video(video_path: str | None, downloaded: bool, keep: bool) -> None:
    """Delete the downloaded video file to save disk space.

    Only deletes when:
    - video_path is set
    - The file was actually downloaded (not a local file)
    - --keep-video was NOT passed
    """
    if not video_path or not downloaded or keep:
        return
    p = Path(video_path)
    if p.exists():
        size_mb = p.stat().st_size / (1024 * 1024)
        try:
            p.unlink()
            print(f"[watch] cleaned up video file ({size_mb:.0f} MB)", file=sys.stderr)
        except OSError as exc:
            print(f"[watch] warning: could not delete video: {exc}", file=sys.stderr)


def main() -> int:
    # Start timing
    timer = StatsTimer()
    timer.__enter__()
    
    ap = argparse.ArgumentParser(
        prog="watch",
        description="Download a video, extract auto-scaled frames, and surface the transcript.",
    )
    ap.add_argument("source", help="Video URL or local file path")
    ap.add_argument("--max-frames", type=int, default=None, help="Override frame cap")
    ap.add_argument("--resolution", type=int, default=512, help="Frame width in pixels (default 512)")
    ap.add_argument("--fps", type=float, default=None, help="Override auto-fps")
    ap.add_argument(
        "--detail",
        choices=["transcript", "transcript-moments", "efficient", "balanced", "token-burner"],
        default=None,
        help="Fidelity/speed dial: transcript (no frames), efficient (fast keyframes, cap 50), "
             "balanced (scene, cap 100), token-burner (scene, uncapped).",
    )
    ap.add_argument(
        "--timestamps",
        type=str,
        default=None,
        help="Comma-separated absolute timestamps (SS, MM:SS, HH:MM:SS) to grab a frame at, "
             "e.g. transcript-flagged 'look here' moments. Added on top of the detail frames "
             "(reserved against the cap); with --detail transcript these become the only frames.",
    )
    ap.add_argument("--start", type=str, default=None, help="Range start (SS, MM:SS, or HH:MM:SS)")
    ap.add_argument("--end", type=str, default=None, help="Range end (SS, MM:SS, or HH:MM:SS)")
    ap.add_argument("--out-dir", type=str, default=None, help="Working directory (default: tmp)")
    ap.add_argument(
        "--no-whisper",
        action="store_true",
        help="Disable Whisper fallback. Report frames-only if no captions available.",
    )
    ap.add_argument(
        "--whisper",
        choices=["groq", "openai"],
        default=None,
        help="Force a specific Whisper backend. Default: prefer Groq, fall back to OpenAI.",
    )
    ap.add_argument(
        "--no-dedup",
        action="store_true",
        help="Disable near-duplicate frame removal. Keeps visually identical "
             "frames (static screen recordings, held slides, paused video) instead of collapsing them.",
    )
    ap.add_argument(
        "--keep-video",
        action="store_true",
        help="Keep the downloaded video file after frame extraction (default: delete to save disk).",
    )
    ap.add_argument(
        "--output",
        choices=["markdown", "json", "both"],
        default="both",
        help="Output format: both (default, markdown + report.json), markdown, or json.",
    )
    ap.add_argument(
        "--auto-moments",
        action="store_true",
        help="Generate LLM prompt for key moment detection from transcript.",
    )
    ap.add_argument(
        "--max-moments",
        type=int,
        default=15,
        help="Maximum key moments to identify (default 15, used with --auto-moments).",
    )
    ap.add_argument(
        "--min-moments",
        type=int,
        default=None,
        help="Minimum moments for transcript-moments mode (default from config, typically 50).",
    )
    ap.add_argument(
        "--stats",
        action="store_true",
        help="Include analysis stats in output (processing time, frames, tokens, etc.).",
    )
    ap.add_argument(
        "--stats-format",
        choices=["telegram", "compact"],
        default="telegram",
        help="Stats output format (default: telegram).",
    )
    args = ap.parse_args()

    config = get_config()
    detail = args.detail or str(config["detail"])
    configured_cap = frame_cap(detail)
    if args.max_frames is not None:
        max_frames = args.max_frames
    else:
        max_frames = configured_cap
    if max_frames is not None and max_frames < 1:
        raise SystemExit("--max-frames must be greater than zero")
    budget_cap = max_frames if max_frames is not None else 100
    cue_timestamps = parse_timestamps(args.timestamps)

    # Resolve min_moments for transcript-moments mode
    min_moments = args.min_moments or config.get("min_moments", DEFAULT_MIN_MOMENTS)

    if args.out_dir:
        work = Path(args.out_dir).expanduser().resolve()
    else:
        work = Path(tempfile.mkdtemp(prefix="watch-"))
    work.mkdir(parents=True, exist_ok=True)
    print(f"[watch] working dir: {work}", file=sys.stderr)

    url_source = is_url(args.source)
    dl: dict = {"subtitle_path": None, "info": {}, "downloaded": False}
    transcript_segments: list[dict] = []
    transcript_text: str | None = None
    transcript_source: str | None = None
    video_path: str | None = None

    if url_source:
        print("[watch] checking metadata/captions via yt-dlp…", file=sys.stderr)
        dl = fetch_captions(args.source, work / "download")
        if dl.get("subtitle_path"):
            try:
                if dl["subtitle_path"].endswith(".json3"):
                    transcript_segments = parse_json3(dl["subtitle_path"])
                    transcript_source = "captions (json3)"
                else:
                    transcript_segments = parse_vtt(dl["subtitle_path"])
                    transcript_source = "captions (vtt)"
                transcript_text = format_transcript(transcript_segments)
            except Exception as exc:
                print(f"[watch] subtitle parse failed: {exc}", file=sys.stderr)
                transcript_segments = []

    # --timestamps needs the video for frame grabs, so it overrides the
    # transcript-mode download skip (and forces a full, not audio-only, fetch).
    # transcript-moments: need video only if key_moments.json exists (re-run)
    moments_json_path = work / "key_moments.json"
    has_moments = detail == "transcript-moments" and moments_json_path.exists()
    audio_only = detail == "transcript" and not cue_timestamps
    need_video = not (detail == "transcript" and transcript_segments and not cue_timestamps)
    # For transcript-moments first run (no key_moments.json yet), skip video download
    if detail == "transcript-moments" and not has_moments and transcript_segments:
        need_video = False
    # Pass existing subtitle to download_url() to prevent 429 re-download
    existing_sub = dl.get("subtitle_path") if dl.get("subtitle_path") else None
    if need_video:
        if url_source:
            print(
                "[watch] downloading audio via yt-dlp…" if audio_only
                else "[watch] downloading video via yt-dlp…",
                file=sys.stderr,
            )
            dl = download(
                args.source,
                work / "download",
                audio_only=audio_only,
                existing_subtitle=existing_sub,
            )
        else:
            print("[watch] using local file…", file=sys.stderr)
            dl = download(args.source, work / "download")
        video_path = dl["video_path"]

    meta = get_metadata(video_path) if video_path else {
        "duration_seconds": float((dl.get("info") or {}).get("duration") or 0),
        "width": None,
        "height": None,
        "codec": None,
        "has_audio": False,
    }
    full_duration = meta["duration_seconds"]

    start_sec = parse_time(args.start)
    end_sec = parse_time(args.end)

    if start_sec is not None and start_sec < 0:
        raise SystemExit("--start must be non-negative")
    if end_sec is not None and start_sec is not None and end_sec <= start_sec:
        raise SystemExit("--end must be greater than --start")
    if full_duration > 0 and start_sec is not None and start_sec >= full_duration:
        raise SystemExit(f"--start {start_sec:.1f}s is past end of video ({full_duration:.1f}s)")

    effective_start = start_sec if start_sec is not None else 0.0
    effective_end = end_sec if end_sec is not None else full_duration
    effective_duration = max(0.0, effective_end - effective_start)
    focused = start_sec is not None or end_sec is not None

    if focused:
        fps, target = auto_fps_focus(effective_duration, max_frames=budget_cap)
    else:
        fps, target = auto_fps(effective_duration, max_frames=budget_cap)
    if args.fps is not None:
        fps = min(args.fps, MAX_FPS)
        target = max(1, int(round(fps * effective_duration)))

    if transcript_segments and focused:
        transcript_segments = filter_range(transcript_segments, start_sec, end_sec)
        transcript_text = format_transcript(transcript_segments)

    scope = (
        f"{format_time(effective_start)}-{format_time(effective_end)} ({effective_duration:.1f}s)"
        if focused else f"full {effective_duration:.1f}s"
    )
    frames: list[dict] = []
    frame_meta: dict = {"engine": "none", "candidate_count": 0, "selected_count": 0, "fallback": False}
    cue_frames: list[dict] = []
    cue_meta: dict = {}

    # Transcript cues are pinned: extracted first and counted against the cap so
    # the detail engine never evicts the moments the user explicitly asked for.
    if cue_timestamps and video_path:
        cue_frames, cue_meta = extract_at_timestamps(
            video_path,
            work / "frames",
            cue_timestamps,
            resolution=args.resolution,
            max_frames=max_frames,
            start_seconds=start_sec,
            end_seconds=end_sec,
        )
        if cue_meta.get("dropped_out_of_window"):
            print(
                f"[watch] {cue_meta['dropped_out_of_window']} cue timestamp(s) outside the "
                "focus range — dropped",
                file=sys.stderr,
            )

    detail_budget = max_frames if max_frames is None else max(0, max_frames - len(cue_frames))

    # ── Transcript-moments mode: extract frames at LLM-identified timestamps ──
    if detail == "transcript-moments":
        if has_moments and video_path:
            # Re-run: key_moments.json exists — extract frames at those timestamps
            moments_data = json.loads(moments_json_path.read_text())
            moment_timestamps = []
            for m in moments_data:
                ts = m.get("timestamp", 0)
                if isinstance(ts, str):
                    parts = ts.strip().split(":")
                    if len(parts) == 2:
                        ts = int(parts[0]) * 60 + float(parts[1])
                    elif len(parts) == 3:
                        ts = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                    else:
                        ts = float(ts)
                moment_timestamps.append(float(ts))
            moment_timestamps = sorted(set(moment_timestamps))

            print(
                f"[watch] transcript-moments: extracting {len(moment_timestamps)} frames "
                f"at LLM-identified timestamps…",
                file=sys.stderr,
            )
            frames, frame_meta = extract_at_timestamps(
                video_path,
                work / "frames",
                moment_timestamps,
                resolution=args.resolution,
                max_frames=None,  # uncapped — extract all moments
                start_seconds=start_sec,
                end_seconds=end_sec,
            )
            # Mark all as transcript-cue reason
            for f in frames:
                f["reason"] = "transcript-cue"
        else:
            # First run: generate prompt for agent, skip frame extraction
            from transcript_moments import format_transcript_for_analysis, generate_prompt

            transcript_for_analysis = format_transcript_for_analysis(transcript_segments)
            info = dl.get("info") or {}
            moments_prompt = generate_prompt(
                transcript_for_analysis,
                info,
                max_moments=min_moments,
                min_moments=min_moments,
            )
            moments_prompt_path = work / "moments_prompt.txt"
            moments_prompt_path.write_text(moments_prompt, encoding="utf-8")
            print(
                f"[watch] transcript-moments: first run — prompt written to {moments_prompt_path}",
                file=sys.stderr,
            )
            print(
                f"[watch] Agent workflow:", file=sys.stderr,
            )
            print(
                f"  1. Read {moments_prompt_path}", file=sys.stderr,
            )
            print(
                f"  2. Analyze transcript, identify {min_moments}+ key moments", file=sys.stderr,
            )
            print(
                f"  3. Write moments as JSON to {moments_json_path}", file=sys.stderr,
            )
            print(
                f"  4. Re-run watch.py with same args to extract frames", file=sys.stderr,
            )

    elif detail != "transcript" and video_path and detail_budget != 0:
        cap_label = "unlimited" if detail_budget is None else str(detail_budget)
        engine_label = "keyframes" if detail == "efficient" else "scene-aware frames"
        print(
            f"[watch] extracting {engine_label} over {scope} "
            f"(target {target}, cap {cap_label})…",
            file=sys.stderr,
        )
        if detail == "efficient":
            frames, frame_meta = extract_keyframes(
                video_path,
                work / "frames",
                resolution=args.resolution,
                max_frames=detail_budget,
                start_seconds=start_sec,
                end_seconds=end_sec,
                dedup=not args.no_dedup,
            )
        elif detail == "token-burner":
            frames, frame_meta = extract_two_pass(
                video_path,
                work / "frames",
                fps=fps,
                target_frames=target,
                resolution=args.resolution,
                max_frames=None,  # Uncapped
                start_seconds=start_sec,
                end_seconds=end_sec,
                dedup=not args.no_dedup,
            )
        else:  # balanced
            frames, frame_meta = extract_scene_or_uniform(
                video_path,
                work / "frames",
                fps=fps,
                target_frames=target,
                resolution=args.resolution,
                max_frames=detail_budget,
                start_seconds=start_sec,
                end_seconds=end_sec,
                dedup=not args.no_dedup,
            )

    if cue_frames:
        frames = merge_frames(frames, cue_frames)

    if not transcript_segments and dl.get("subtitle_path"):
        try:
            all_segments = parse_vtt(dl["subtitle_path"])
            transcript_segments = filter_range(all_segments, start_sec, end_sec) if focused else all_segments
            transcript_text = format_transcript(transcript_segments)
            transcript_source = "captions"
        except Exception as exc:
            print(f"[watch] subtitle parse failed: {exc}", file=sys.stderr)

    if not transcript_segments and not args.no_whisper and video_path and meta.get("has_audio"):
        backend, api_key = load_api_key(args.whisper)
        if backend and api_key:
            try:
                all_segments, used_backend = transcribe_video(
                    video_path,
                    work / "audio.mp3",
                    backend=backend,
                    api_key=api_key,
                )
                transcript_segments = filter_range(all_segments, start_sec, end_sec) if focused else all_segments
                transcript_text = format_transcript(transcript_segments)
                transcript_source = f"whisper ({used_backend})"
            except SystemExit as exc:
                print(f"[watch] whisper fallback failed: {exc}", file=sys.stderr)
        else:
            hint = (
                f"--whisper {args.whisper} was set but the matching API key is missing"
                if args.whisper else
                "no subtitles and no Whisper API key found"
            )
            setup_py = SCRIPT_DIR / "setup.py"
            print(
                f"[watch] {hint} — run `python3 {setup_py}` to enable the Whisper fallback",
                file=sys.stderr,
            )
    elif not transcript_segments and video_path and not meta.get("has_audio"):
        print("[watch] no audio stream found — proceeding without transcription", file=sys.stderr)

    # ── Cleanup ─────────────────────────────────────────────────────
    # Delete downloaded video — everything that needed it (frames, whisper
    # audio) is done.  Local files are never touched.
    _cleanup_video(video_path, dl.get("downloaded", False), args.keep_video)

    # Clean up whisper audio chunks to save a few extra MB.
    audio_tmp = work / "audio.mp3"
    if audio_tmp.exists():
        try:
            audio_tmp.unlink()
        except OSError:
            pass
    chunks_dir = work / "audio" / "chunks"
    if chunks_dir.exists():
        shutil.rmtree(chunks_dir, ignore_errors=True)

    info = dl.get("info") or {}

    # ── Build structured report ──────────────────────────────────────
    warnings = []
    if detail == "token-burner" and len(frames) > 250:
        warnings.append(
            f"Token-burner detail selected {len(frames)} frames. "
            "This may use a large number of image tokens."
        )
    if not focused and full_duration > 600 and detail not in ("transcript", "transcript-moments", "token-burner"):
        mins = int(full_duration // 60)
        warnings.append(
            f"This is a {mins}-minute video. Frame coverage is sparse at this length "
            f"under `{detail}` detail — its cap spreads thin across the full clip. For better results, "
            "re-run with `--start HH:MM:SS --end HH:MM:SS` to zoom into a section, or use "
            "`--detail token-burner` to keep every scene-change frame across the whole video."
        )
    if not focused and full_duration > 1200:
        warnings.append(
            "⚠️ Long video (>20 min): terminal output may be truncated. "
            "Use `--output both` to ensure a JSON backup is written to the work dir."
        )
    if not transcript_segments:
        if detail == "transcript":
            warnings.append(
                "No transcript available at transcript detail. Captions were missing and Whisper was "
                "unavailable or failed, so there is no visual fallback here. Re-run with "
                "`--detail balanced` for frames."
            )
        elif focused and dl.get("subtitle_path"):
            warnings.append(
                f"No transcript lines fell inside {format_time(effective_start)} → {format_time(effective_end)}."
            )
        else:
            setup_py = SCRIPT_DIR / "setup.py"
            warnings.append(
                "No transcript available — proceed with frames only. "
                "Captions were missing and the Whisper fallback was unavailable "
                "(no API key set, or `--no-whisper` was used). "
                f"Run `python3 {setup_py}` to enable Whisper, then re-run."
            )

    # ── Auto-moments: Generate LLM prompt for key moment detection ──
    key_moments_data: list[dict] = []
    key_moment_stats_data: dict | None = None
    moments_prompt_path: Path | None = None

    # Load key_moments.json for transcript-moments mode (already extracted)
    _VALID_MOMENT_REASONS = {
        "proper_noun", "claim", "deictic", "speaker_id",
        "visual_context", "entity", "topic_transition", "key_argument", "unknown",
    }
    if detail == "transcript-moments" and moments_json_path.exists():
        try:
            key_moments_data = json.loads(moments_json_path.read_text())
            # Normalize invalid reason values to prevent Pydantic validation errors
            for m in key_moments_data:
                r = m.get("reason", "unknown")
                if r not in _VALID_MOMENT_REASONS:
                    print(
                        f"[watch] warning: invalid moment reason '{r}', normalizing to 'unknown'",
                        file=sys.stderr,
                    )
                    m["reason"] = "unknown"
            print(
                f"[watch] loaded {len(key_moments_data)} key moments from {moments_json_path}",
                file=sys.stderr,
            )
            # Calculate stats
            by_reason: dict[str, int] = {}
            by_priority: dict[int, int] = {}
            for m in key_moments_data:
                reason = m.get("reason", "unknown")
                priority = m.get("priority", 3)
                by_reason[reason] = by_reason.get(reason, 0) + 1
                by_priority[priority] = by_priority.get(priority, 0) + 1
            key_moment_stats_data = {
                "total": len(key_moments_data),
                "by_reason": by_reason,
                "by_priority": by_priority,
            }
        except Exception as exc:
            print(f"[watch] failed to load key_moments.json: {exc}", file=sys.stderr)

    if args.auto_moments and transcript_segments:
        # Generate LLM prompt for moment detection
        transcript_for_analysis = format_transcript_for_analysis(transcript_segments)
        moments_prompt = generate_prompt(
            transcript_for_analysis,
            info,
            max_moments=args.max_moments,
            min_moments=min_moments,
        )

        # Write prompt to file for agent to process
        moments_prompt_path = work / "moments_prompt.txt"
        moments_prompt_path.write_text(moments_prompt, encoding="utf-8")

        # Check if agent already provided moments (from previous run)
        moments_json_path = work / "key_moments.json"
        if moments_json_path.exists():
            try:
                key_moments_data = json.loads(moments_json_path.read_text())
                # Normalize invalid reason values
                for m in key_moments_data:
                    r = m.get("reason", "unknown")
                    if r not in _VALID_MOMENT_REASONS:
                        m["reason"] = "unknown"
                print(
                    f"[watch] loaded {len(key_moments_data)} key moments from existing file",
                    file=sys.stderr,
                )
            except Exception as exc:
                print(f"[watch] failed to load key_moments.json: {exc}", file=sys.stderr)
                key_moments_data = []

        # Calculate stats
        if key_moments_data:
            by_reason: dict[str, int] = {}
            by_priority: dict[int, int] = {}
            for m in key_moments_data:
                reason = m.get("reason", "unknown")
                priority = m.get("priority", 3)
                by_reason[reason] = by_reason.get(reason, 0) + 1
                by_priority[priority] = by_priority.get(priority, 0) + 1
            key_moment_stats_data = {
                "total": len(key_moments_data),
                "by_reason": by_reason,
                "by_priority": by_priority,
            }

    report = build_report(
        source=args.source,
        title=info.get("title"),
        uploader=info.get("uploader"),
        duration=full_duration,
        width=meta.get("width"),
        height=meta.get("height"),
        codec=meta.get("codec"),
        has_audio=meta.get("has_audio", False),
        detected_language=dl.get("detected_language"),
        # Channel stats
        channel_id=info.get("channel_id"),
        channel_url=info.get("channel_url"),
        channel_follower_count=info.get("channel_follower_count"),
        channel_is_verified=info.get("channel_is_verified", False),
        uploader_id=info.get("uploader_id"),
        uploader_url=info.get("uploader_url"),
        # Video stats
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        comment_count=info.get("comment_count"),
        upload_date=info.get("upload_date"),
        tags=info.get("tags"),
        categories=info.get("categories"),
        detail=detail,
        focus_start=effective_start if focused else None,
        focus_end=effective_end if focused else None,
        frames=frames,
        frame_meta=frame_meta if frame_meta.get("selected_count", 0) > 0 else None,
        transcript_source=transcript_source or ("none" if not transcript_segments else "captions"),
        transcript_segments=transcript_segments,
        transcript_text=transcript_text,
        key_moments=key_moments_data,
        key_moment_stats=key_moment_stats_data,
        warnings=warnings,
    )

    # ── Output ───────────────────────────────────────────────────────
    output_mode = args.output

    if output_mode in ("markdown", "both"):
        # When output is "both", use compact mode to avoid terminal truncation
        # (full transcript is in report.json)
        print(report.to_markdown(compact=(output_mode == "both")))
        # Footer
        print()
        print("---")
        footer = (
            f"_Work dir: `{work}` — frames + transcript retained, video auto-cleaned._"
            if not args.keep_video else
            f"_Work dir: `{work}` — all files retained (--keep-video)._"
        )
        print(footer)

    if output_mode in ("json", "both"):
        json_path = work / "report.json"
        report.to_json_file(json_path)
        if output_mode == "json":
            # JSON-only: print path so agent can find it
            print(f"Report written to: {json_path}")
        else:
            print(f"\n_Report JSON: `{json_path}`_")

    # ── Auto-moments output ──────────────────────────────────────────
    if args.auto_moments and moments_prompt_path:
        if key_moments_data:
            # Moments already loaded
            print(f"\n✅ {len(key_moments_data)} key moments loaded from `{moments_json_path}`")
            print("\nNext steps for agent:")
            print("1. Extract frames at key moment timestamps (if not already extracted)")
            print("2. Call vision_analyze on each frame with moment.question")
            print("3. Update key_moments.json with vision results")
            print("4. Re-run watch.py --auto-moments to include results in report")
        else:
            # Need agent to process prompt
            print(f"\n📝 LLM prompt written to: `{moments_prompt_path}`")
            print("\nAgent workflow:")
            print(f"1. Read the prompt from `{moments_prompt_path}`")
            print("2. Analyze transcript and identify key moments")
            print(f"3. Write moments as JSON to `{moments_json_path}`")
            print("4. Re-run watch.py --auto-moments to include results in report")

    # ── Stats output ────────────────────────────────────────────────
    if args.stats:
        timer.__exit__(None, None, None)
        stats = collect_stats(work)
        stats.processing_time = timer.elapsed
        
        if args.stats_format == "telegram":
            print("\n" + format_stats_telegram(stats))
        else:
            print("\n" + format_stats_compact(stats))
        
        # Save stats to file
        stats_path = work / "stats.json"
        stats_path.write_text(json.dumps(stats.to_dict(), indent=2))
        print(f"_Stats saved to: `{stats_path}`_")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
