# Namma Suvidha Demo Video — Production Report

**Production date:** 31 October 2026  
**Project:** `D:\alliance-one-hackathon-2026`  
**Primary output:** `brag\exports\Namma-Suvidha-Demo-70s.mp4`  
**Short output:** `brag\exports\Namma-Suvidha-Demo-30s.mp4`

## Summary

Two finished 16:9 product demonstration edits were exported: a 70-second master and a 30-second short. The edits use the official logo reveal, a genuine capture of the current Citizen Portal, a clearly labeled Google Flow restroom/device illustration, product-status graphics, local Kokoro narration, and an original locally synthesized ambient music bed. Non-deployed capabilities are labeled as concepts or proposed workflows.

## Reference assets discovered

The source inventory and suitability notes are also in [`brag/documentation/asset-inventory.csv`](../brag/documentation/asset-inventory.csv). Originals were left in place; selected media were copied into `brag`.

| Asset | Properties | Review and use |
|---|---|---|
| `public/logo-reveal.mp4` | 8.0 s, 1920×1080, 16:9, AAC stereo | Official logo reveal; opening footage and source for the verified full-logo end card. Source audio muted. |
| `namma-suvidha-logo-animation.html` | HTML reference | Brand reference; not used as a rendered source. |
| `citizen-portal-1920.png` / `citizen-portal-capture.png` | 1920×1080, 16:9, no audio | Genuine current application capture; cropped copy used in the UI scene. No synthetic facility-result pins were added. |
| `citizen-portal-landing.png` | 1264×650, 1.94:1, no audio | Genuine screenshot reference; not used in the final cut because the lower map area is cropped. |
| `Animate_civic_tech_feedback_video_e3ce66b4_1080p.mp4` | 9.963 s, 1920×1080, 16:9, AAC stereo | Google Flow illustration of the citizen/restroom and feedback panel. Used in short excerpts, muted, with its malformed generated panel subtitle covered by an overlay. The citizen and restroom remain consistent across both excerpts. |
| `Continue_animation_video_generation_05cc7124_1080p.mp4` | 9.963 s, 1920×1080, 16:9, AAC stereo | Google Flow pipeline concept; malformed labels and graphics; retained as a reference only and excluded from the final video. |
| `Screen Recording 2026-10-24 150056.mp4` | 63.488 s, 1330×624, 2.13:1, AAC stereo | Previewed; unrelated operational telemetry dashboard; excluded. |
| `WhatsApp Video 2026-10-31 at 1.47.49 AM.mp4` | 8.0 s, 1920×1080, 16:9, AAC stereo | Duplicate of the official logo reveal by size and visual review; no duplicate copy made. |
| `Standard recording 4.mp3` | 816.993 s, audio only, stereo 48 kHz | Purpose unknown; not auditioned or used. |
| `1625131068617.jpg` | 701×1024, portrait, no audio | Unrelated tower illustration; excluded. |
| BBMP toilet dataset CSV (`4e4a3896-2880-40dc-874d-01276dfb4f61.csv`) | CSV data, no duration/resolution/audio | Loader source for the BBMP integration; used for product verification, not composited as invented on-screen facility data. |

No Citizen Portal video recording, physical IoT device footage, Government Dashboard recording, or verified evaluator workflow recording was found. The Citizen Portal is shown as a genuine application screenshot, not represented as a live screen recording.

## BRAG capabilities and workflow

- Inspected the installed `brag` and HyperFrames skill documentation, installed CLI help, and supported workflow before production. BRAG routes video creation through HyperFrames; the supported general-video workflow was used for the longer runtime rather than inventing a BRAG command.
- Used HyperFrames CLI 0.8.223 to validate and render two HTML compositions at 1920×1080 and 30 fps. The editable compositions are `brag/project-files/index.html` and `brag/project-files/compositions/short.html`.
- Used HyperFrames local Kokoro TTS (`af_nova`, `en-us`) to create both narration tracks. Used FFmpeg for the original ambient bed, local audio mix, source-frame extraction, metadata checks, full decode, black-frame scan, and review sheets.
- No copyrighted commercial music was used. The local ambient bed is an original synthesized track at `brag/music/namma-original-ambient.wav`.
- Claude Opus 5.5 was not available in this Codex session. Planning and production decisions were made with the available Codex model.

## Scenes completed

| Master time | Scene | Content and truth labeling |
|---|---|---|
| 0–6 s | Brand opening | Official logo animation and “Find public toilets you can actually trust.” |
| 6–14 s | The real problem | Labeled illustrative citizen/restroom scene; explains that a location does not establish current usability. |
| 14–27 s | Citizen discovery | Genuine current Citizen Portal capture, map view, radius controls, and infrastructure-record context. Copy clarifies that inventory does not certify live cleanliness or availability. |
| 27–41 s | Feedback device | Google Flow concept shows a red NO response and the microphone/optional voice idea. Panel, character, and restroom are illustrative; hardware is not deployed. |
| 41–54 s | Voice pipeline | Proposed device → wireless → backend → speech-to-text → AI-assisted classification → structured issue. Copy says AI does not set official scores or make enforcement decisions. |
| 54–61 s | Government monitoring | Local in-memory issue API prototype and human review concept. Explicitly says there is no deployed Government Dashboard; test email is not delivered. |
| 61–64 s | Evaluator verification | Status card says end-to-end evaluator evidence submission has not been demonstrated. |
| 64–70 s | Brand close | Full official logo artwork, “NAMMA SUVIDHA,” and “One city. Better facilities. More dignity.” |

The short edit compresses the same story into 0–3 s brand, 3–6 s problem, 6–15 s portal, 15–20 s device, 20–24 s proposed pipeline, 24–27 s local government APIs, and 27–30 s brand close.

## Implemented versus illustrative

**Implemented or locally demonstrated:** The current Citizen Portal interface and its radius controls; the BBMP CSV loader/integration; and backend issue lifecycle APIs. A local nearby-query against the BBMP source returned 432 records during verification. The on-screen Portal is a genuine capture, but it does not show that query’s results.

**Local prototype limitations:** Government-side APIs use in-memory repositories in the demo. There is no deployed Government Dashboard, production maintenance operation, or delivered test email. The visual officer review is explanatory artwork, not a filmed dashboard interaction.

**Illustrative or proposed:** Physical feedback hardware, wireless device transmission, microphone capture, transcription, AI-assisted complaint classification, and the connected evaluator verification workflow. These are explicitly marked as concepts/proposed or not deployed. No feature claims government endorsement or automated enforcement.

## Voiceover and music

- Main narration: local Kokoro TTS, `af_nova`, English (US), 64.1-second generated narration, mixed to the 70-second edit with a short music-only logo tail.
- Short narration: same local voice and language, 29.0-second narration, mixed to the 30-second edit.
- Music: original locally synthesized ambient bed, faded at the end of each mix; no commercial or unlicensed track.
- The source Flow and logo-video audio were muted. Audio is mixed into a single stereo track in each export.
- On-screen copy and labels are used as minimal captions. Full word-for-word accessibility subtitles (`.srt`/`.vtt`) were not produced.

## Quality control

- Reviewed frame sheets sampled every two seconds across both complete timelines, plus full-resolution checks of the feedback device and final logo scenes.
- Confirmed the same illustrative citizen and restroom are used across connected scenes; the device retains green/yellow/red buttons and a separate microphone. The generated misspelled subtitle is fully covered in the final render.
- Checked logo artwork, visible text, scene boundaries, the scoped pipeline disclaimer, and final slogan placement. No black intervals of 0.1 seconds or longer were reported by FFmpeg’s black-frame scan.
- FFmpeg decoded both complete MP4s without errors. `ffprobe` confirmed H.264 video, AAC stereo audio at 48 kHz, 1920×1080, 30 fps, and exact 70.0/30.0-second durations.
- Audio stream checks found non-silent program levels and no unintended silent gaps. HyperFrames validated both render artifacts. Its post-render bookkeeping emitted an `EISDIR` state-lock warning after successful artifact validation; the exported files themselves decoded and played through the full duration.

## Export settings and locations

| File | Duration | Video | Audio | Size |
|---|---:|---|---|---:|
| `brag/exports/Namma-Suvidha-Demo-70s.mp4` | 70.0 s | MP4, H.264, 1920×1080, 30 fps | AAC, stereo, 48 kHz | 29.1 MB |
| `brag/exports/Namma-Suvidha-Demo-30s.mp4` | 30.0 s | MP4, H.264, 1920×1080, 30 fps | AAC, stereo, 48 kHz | 18.1 MB |

Editable project files, copies of source media, generated narration, mixes, original ambient music, references, and inventory are organized under `brag/`.

## Remaining issues

1. A real Citizen Portal screen recording with working geolocation and actual nearby results was unavailable. Browser geolocation was denied during capture, so the finished video uses the real UI screenshot and does not invent result data.
2. No physical feedback device or deployed voice/AI pipeline exists in the material reviewed; these scenes remain illustrative/proposed.
3. No Government Dashboard recording or verified end-to-end evaluator workflow was found. These limitations are stated in the film.
4. Full transcript captions are not included. Add an accessibility subtitle file in a future revision if required.
5. HyperFrames reports non-blocking composition lint warnings (40 for the master and 8 for the short) and a post-render state-lock bookkeeping warning. Both exported artifacts were validated by HyperFrames and fully decoded after rendering.
