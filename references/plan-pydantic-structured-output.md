# Watch Skill — Pydantic Structured Output (COMPLETED)

> Implemented 2026-07-11. Commit: `be73cba` on `github.com/m1crodevil/hermes-video`.

## What was done

Replaced 50+ free-form `print()` calls in `watch.py` with validated Pydantic v2 models. Output now serializes to both JSON (for agent pipelines) and comprehensive markdown (for humans).

### Models (`scripts/models.py`)

| Model | Purpose |
|-------|---------|
| `WatchReport` | Top-level container — metadata, frames, transcript, warnings |
| `VideoMetadata` | Source, title, uploader, duration, resolution, codec |
| `Frame` | Path, timestamp, reason, deduped flag |
| `FrameStats` | Candidates, selected, deduped, engine, selection_rate |
| `TranscriptSegment` | Start/end, text, words (JSON3 word-level timing) |
| `WordTiming` | Single word with ASR confidence |
| `FocusRange` | Optional start/end for partial analysis |

Computed fields: `duration_fmt`, `timestamp_fmt`, `resolution`, `start_fmt`, `end_fmt`.

### CLI flag

`--output markdown|json|both` (default: `markdown`)

- `markdown` → human-readable report to stdout (tables, timeline, transcript)
- `json` → writes `report.json` to work dir
- `both` → markdown stdout + JSON file

### `build_report()` helper

Bridges the existing dict-based pipeline to Pydantic models:

```python
report = build_report(
    source=url, title=info["title"], duration=meta["duration_seconds"],
    frames=frames, frame_meta=frame_meta,
    transcript_source="json3", transcript_segments=segments,
)
```

### Tests

30 tests in `tests/test_models.py` — all model creation, computed fields, serialization, markdown rendering, and `build_report()` bridge.

### Pitfalls discovered

1. **`read_file` cannot handle binary images** — returns "Cannot read binary file". Use `vision_analyze` for JPEG frames. This is a Hermes-specific limitation.
2. **Pydantic `@computed_field` must come before `@property`** — decorator order matters.
3. **`use_enum_values=True`** on BaseModel stores raw strings, not Enum instances — simpler for downstream code but loses enum methods.
