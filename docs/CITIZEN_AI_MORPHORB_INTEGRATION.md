# Namma Suvidha — Citizen Portal AI Thinking Orb Integration

## 1. Overview
The Citizen Portal has been upgraded with an interactive AI-powered search assistant using the **MorphOrb** (`anark17r/ai-thiking-orb-and-input`) component. The previous static presentation area is now an animated, high-performance canvas-based 3D thinking orb integrated directly with Namma Suvidha's live BBMP OpenStreetMap discovery pipeline.

---

## 2. Key Architecture & Customizations

### 2.1 Brand Identity & Design System
Aligned strictly with the official Namma Suvidha civic-tech palette:
- **Deep Petrol Teal:** `#123C3A` (Primary interactive surfaces, headings, branding accents)
- **Warm Ivory:** `#F2EEE5` (Answer containers, highlights, ambient background)
- **Terracotta Accent:** `#D18B55` (Active orbital rings, status markers, loading telemetry)
- **Dark Charcoal:** `#29312F` (High-contrast typography)

### 2.2 Component Implementation: `MorphOrb`
Located at `frontend/src/components/ui/ai-thiking-orb-and-input.tsx`:
- **3D Particle Sphere:** Native HTML5 2D Canvas rendering a 3D spherical particle cloud using Fibonacci distribution with perspective depth sorting and dynamic rotational velocity.
- **Three Core States:**
  1. `idle`: Interactive input bar with animated pulsing ambient orb and quick preset query chips.
  2. `thinking`: Smooth scale transition, accelerated particle rotation, and live telemetry status ("Analyzing Sanitation Telemetry…").
  3. `answered`: Dynamic answer card unfold displaying the factual response, verified tags, and direct actions.
- **Accessibility & Motion:**
  - Full keyboard navigation (`Enter` to submit, `Escape` to reset, accessible aria labels).
  - Honors `prefers-reduced-motion: reduce` by disabling heavy particle rotation and CSS glow scaling.
  - Proper timer and `requestAnimationFrame` lifecycle cleanups preventing memory leaks.

### 2.3 Global Animations (`frontend/src/index.css`)
Added CSS classes:
- `.mo-orb-container`: Centered flexbox positioning with drop shadows.
- `.mo-orb-canvas`: Particle canvas container with smooth transitions.
- `.mo-orb-glow`: Keyframe pulsing radial aura (`mo-pulse-glow`).
- `.mo-card-unfold`: Spring-like slide and fade entry (`mo-card-unfold-anim`).

---

## 3. Real Discovery & Natural Language Intelligence

The component is directly wired into `CitizenHome.tsx` via `handleAiQuery`:
1. **Natural Language Radius Detection:**
   - `"500m"` / `"half km"` &rarr; Automatically switches radius to 500m.
   - `"1 km"` / `"1km"` &rarr; Automatically switches radius to 1,000m.
   - `"2 km"` / `"2km"` &rarr; Automatically switches radius to 2,000m.
   - `"5 km"` / `"5km"` &rarr; Automatically switches radius to 5,000m.
   - `"10 km"` / `"10km"` &rarr; Automatically switches radius to 10,000m.

2. **Sanitation & Inclusivity Filters:**
   - Detects queries asking for wheelchair / accessible / disability accommodations &rarr; enables `wheelchairOnly` filter.
   - Detects queries asking for free / no-fee restrooms &rarr; enables `freeOnly` filter.
   - Detects baby changing tables & public access requirements.

3. **Geocoding & Bengaluru Landmark Resolution:**
   - Built-in coordinates for key Bengaluru hubs (Majestic / Kempegowda, Indiranagar, Jayanagar, Electronic City, Alliance University / Anekal, Malleshwaram, K.R. Market / Chickpet, Whitefield, Koramangala, MG Road).
   - "Near me" / "current location" triggers device GPS coordinates seamlessly.

4. **Truthful & Dynamic Responses:**
   - Discovers real OpenStreetMap / BBMP public facilities.
   - Returns factual counts, closest facility names, geodesic distances, and addresses.
   - Synchronizes the live map view, Leaflet markers, and selected toilet card automatically.

