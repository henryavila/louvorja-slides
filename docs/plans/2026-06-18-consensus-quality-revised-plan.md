# Revised Consensus Quality Plan

Date: 2026-06-18

## Why This Replaces The Previous Phase Order

The original plan treated phase 1 phrase consensus as the MVP and pushed vocal
activity, ROVER-lite, and OCR into later phases. The real gate shows that order
is wrong. The current consensus can be worse than the best individual candidate
and can fragment the timeline even when it removes hard-limit layout failures.

Gate evidence from
`/tmp/louvorja-asr-batch-2026-06-18/phase-history/phase-1/phase1-lyrics-ref-clear-report-20260618T181000Z/`:

- Full set complete: 11/11 videos.
- Hard-limit lines improved: 23 -> 0.
- Slide count regressed: 130 -> 289, ratio 2.223.
- Total lyric lines regressed: 237 -> 543, ratio 2.291.
- Fast transitions regressed: 0 -> 44.
- Auxiliary words regressed: 18 -> 70.
- `Deus e Refugio` reference gate failed: baseline similarity 0.6202, phase
  consensus similarity 0.4341.
- For `Deus e Refugio`, individual candidates beat consensus: `medium-voice-eq`
  and `turbo-denoise` both scored 0.7209 against the reference, while consensus
  scored 0.4341.

## External Research Takeaways

Sources reviewed:

- NIST ROVER:
  https://www.nist.gov/publications/post-processing-system-yield-reduced-word-error-rates-recognizer-output-voting-error
- Music source separation for Whisper lyrics transcription:
  https://arxiv.org/html/2506.15514v1
- Whisper transcription parameters:
  https://github.com/openai/whisper/blob/main/whisper/transcribe.py
- Whisper non-speech hallucinations:
  https://arxiv.org/html/2501.11378v1
- Faster-Whisper VAD integration:
  https://github.com/SYSTRAN/faster-whisper
- Silero VAD:
  https://github.com/snakers4/silero-vad
- Demucs:
  https://github.com/facebookresearch/demucs
- WhisperX forced alignment / VAD concepts:
  https://github.com/m-bain/whisperx
- Audio-to-lyrics alignment survey point:
  https://archives.ismir.net/ismir2021/paper/000007.pdf
- PaddleOCR:
  https://github.com/PaddlePaddle/PaddleOCR
- EasyOCR:
  https://github.com/jaidedai/easyocr
- Video subtitle OCR post-processing:
  https://arxiv.org/html/2503.04058v1

Implications for this project:

1. ROVER-style voting is not the same as greedy phrase stitching. It needs a
   global alignment or word transition network so outputs do not create
   overlapping timeline decisions.
2. For lyrics transcription with Whisper, source separation is most useful when
   it gives better vocal-active segment boundaries. Better boundaries can matter
   more than transcribing the separated stem directly.
3. Whisper can hallucinate on non-speech and can loop/repeat across windows.
   The generation pipeline must treat non-vocal regions and low-confidence
   windows as dangerous, not as neutral input.
4. Vocal separation can add artifacts. It should be a timing/VAD evidence
   source and a candidate source, not automatically trusted as better text.
5. Lyric-video OCR is likely a high-leverage automatic source for the hymn
   videos, but it must be gated by frame-to-frame stability and treated as a
   candidate, not truth.

## Revised Objective

Do not advance to phase 2 as originally written. First turn phase 1 into a
non-regressing automatic selector/consensus engine:

- It must never be worse than the best available individual candidate by the
  available gates.
- It must not fragment slides/timestamps.
- It must preserve all old-process artifacts and effort metrics.
- It must keep reference lyrics evaluation-only unless the user explicitly runs
  lyrics-first mode.

Reference usage rule: reference lyric files may be used only after generation
to score and fail/pass a gate. They must not influence candidate filtering,
candidate selection, phrase scoring, fallback selection, prompts, or generated
text in consensus mode.

User decision after the real gate: vocal separation is the primary stage after
YouTube audio extraction. Practically, every production run should generate the
`htdemucs_ft` vocal stem before transcription and treat vocal-stem candidates as
first-class evidence. The vocal stem is not allowed to bypass fallback gates:
if a vocal candidate is empty, too short, repetitive, or layout-problematic, the
selector must fall back to another eligible automatic candidate.

Vocal-primary validation artifact:
`/tmp/louvorja-asr-batch-2026-06-18/vocal-primary-20260618T1900Z/`.
This run showed why both parts are required: `turbo-vocals` reached 0.8760
similarity for `Deus e Refugio`, but `medium-vocals` failed on two songs and
`turbo-vocals` produced unusably short or repetitive output on some songs.

## Revised Implementation Order

### Phase A: Measurement Before More Generation

Goal: make the report able to explain why a source or consensus won.

Implement:

- Per-source runtime, cache delta, word count, phrase count, low-confidence
  count, repetition score, word-rate, vocal-active coverage, and layout metrics.
- Per-source reference metrics when a reference file exists.
- Per-video source ranking table in `phase-gate-report.md`.
- Consensus decision-density metrics: decision count, overlapping adjacent
  decisions, median start gap, unsupported single-source decisions, and low
  confidence ratio.
- Persist these metrics in JSON so future gates can compare effort and quality.

Gate:

- Full 11-video run required.
- Report must show the best individual candidate, selected phase output, and
  effort for each source.
- No source or decision can be hidden from the report.

### Phase B: Safe Selector Fallback

Goal: stop making output worse while better consensus is built.

Implement:

- Add candidate-level eligibility filters before phrase voting:
  - reject empty or very short candidates;
  - reject candidates with extreme word-rate or phrase-rate;
  - reject candidates with obvious hallucination/repetition;
  - reject candidates whose layout metrics are severe outliers;
  - reject candidates whose automatic confidence/proxy metrics are severe
    outliers.
- Add a whole-candidate fallback:
  - if consensus has high decision density, high overlap, high low-confidence
    ratio, or poor automatic proxy quality, output the best eligible individual
    candidate instead of stitched consensus.
- Re-introduce old-process candidates that empirically helped:
  - `medium-voice-eq`;
  - `turbo-denoise`.
- Penalize single-source phrase winners unless they are temporally isolated and
  do not overlap adjacent accepted decisions.

Gate:

- On any referenced song, phase output must have word similarity at least
  `max(0.80, baseline_similarity - 0.02)` unless the explicit mode is
  exploratory.
- On referenced songs, phase output must not trail the best eligible individual
  candidate by more than 0.02 similarity, but this is evaluated after
  generation and cannot be used to choose that output.
- Robust layout gates remain: hard-line non-regression, bounded slide ratio,
  line ratio, fast transition ratio, auxiliary-word regression, and over-target
  ratio.
- Decision density gate: no overlapping accepted adjacent decision windows and
  median decision start gap must not be below the baseline slide start gap by
  more than 30%.

### Phase C: Vocal-Activity Segmentation

Goal: prevent Whisper from transcribing instrumentals, noise, and silence.

Implement:

- Generate and cache a vocal stem with `htdemucs_ft`.
- Compute vocal-active windows from the stem using RMS energy first; keep Silero
  VAD or faster-whisper VAD as an optional experiment if dependencies are
  acceptable.
- Use those windows as chunk boundaries for original-mix and vocal-stem
  transcription. If the active pywhispercpp binding cannot accept
  `clip_timestamps` directly, physically extract temporary WAV chunks and
  merge their timestamps back into the original timeline.
- Merge neighboring active windows conservatively so phrases are not cut mid
  line.
- Store vocal activity windows and per-window effort/quality metrics.

Gate:

- Less text in instrumental/solo regions.
- Candidate word counts move closer to old best candidates rather than
  exploding.
- For `Deus e Refugio`, no generated "credit/subtitle" tail should appear after
  the final sung region.
- Full 11-video run must improve or maintain robust layout gates and reference
  gate versus Phase B.

### Phase D: Real ROVER-Lite, Not Phrase Stitching

Goal: combine words only inside well-defined, non-overlapping anchor windows.

Implement:

- Build anchor windows from vocal activity plus consensus of candidate phrase
  times.
- For each anchor window, align candidate word sequences with dynamic
  programming.
- Create a word transition network with source weights.
- Weight sources by measured per-song reliability, not fixed preference only.
- Give OCR/caption text higher weight only when it is stable and temporally
  aligned.
- Fall back to the best whole phrase when the word network confidence is low.
- Never allow output windows to overlap or reorder.

Gate:

- Referenced songs must improve over Phase B or fall back to Phase B output.
- Unsupported words cannot appear unless they come from the selected whole
  phrase fallback.
- Repetition/hallucination filters must catch duplicated phrases and credit
  lines.

### Phase E: OCR For Lyric Videos

Goal: exploit videos that visibly contain lyrics without weakening audio-only
songs.

Implement:

- Detect stable text frames at low sample rate first.
- Use PaddleOCR as the preferred local OCR engine; EasyOCR as fallback.
- Deduplicate text by normalized similarity and time.
- Convert stable OCR spans into `video-ocr` candidates.
- Reject OCR when text is unstable, too short, low confidence, or inconsistent
  across frames.

Gate:

- OCR must be listed as used, ignored, or unavailable per video.
- Videos without stable text must be unaffected.
- Lyric-video outputs must improve defined text quality proxies without
  regressing layout gates. Initial proxies: OCR frame-stability ratio,
  OCR/ASR normalized agreement, caption/OCR agreement when captions exist, and
  reference similarity only as a post-generation gate.

## Explicit Non-Goals

- Do not use an LLM for correction, phrase selection, or review.
- Do not use the reference lyric file to generate consensus output.
- Do not depend on `titan-chordpro-lib` at runtime.
- Do not treat vocal stems as inherently better text.
- Do not advance based on hard-line layout success alone.

## Immediate Next Task

Implement Phase A and Phase B before any Phase C/D/E work. The current highest
leverage fix is a safe selector fallback and a larger candidate pool. The
`Deus e Refugio` gate proves `medium-voice-eq` and `turbo-denoise` belong in the
pool; the selector itself must still choose using automatic, non-reference
signals.
