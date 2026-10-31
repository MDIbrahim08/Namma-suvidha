# Namma Suvidha video project

Editable HyperFrames project for the 70-second product demonstration and 30-second short.

## Files

- `index.html` — main composition, 1920×1080 at 30 fps, 70 seconds.
- `short.html` — short composition, 1920×1080 at 30 fps, 30 seconds.
- `assets/` — local render inputs (copied source assets, derived stills, and mixed audio).
- `brag-plan.md` — creative brief and storyboard.
- `VOICEOVER_SCRIPT.md` — narration copy and voice settings.
- `asset-inventory.csv` — media inventory and selection notes.

## Render commands

From the project directory, with HyperFrames 0.8.223 available:

```powershell
npx hyperframes check .
npx hyperframes render . --fps 30 --quality delivery --output ..\exports\Namma-Suvidha-Demo-70s.mp4
npx hyperframes render . --composition compositions/short.html --fps 30 --quality delivery --output ..\exports\Namma-Suvidha-Demo-30s.mp4
```

The main source material is local. `index.html` loads GSAP 3.14.2 from jsDelivr as in the documented HyperFrames minimal composition; the render environment needs access to that script unless it is vendored locally.

## Truth labels

The Citizen Portal image is a genuine app capture with no results, markers, facility names, or ratings. The Flow device footage is generated illustration with its malformed generated subtitle masked. The voice pipeline is explicitly proposed. The government scene describes current backend APIs as a local in-memory demo and does not present a dashboard. The evaluator workflow is called out as not demonstrated end-to-end.
