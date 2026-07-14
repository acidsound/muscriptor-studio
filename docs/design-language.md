# Tactile Signal Studio — Design Language

## Positioning

MuScriptor Studio should feel like a **music instrument with an AI engine**, not like an AI SaaS dashboard.

The primary surface is **Operate**: the user is arranging, selecting, editing, and listening. Generation is a secondary **Command** surface, and clip properties are an **Inspect** surface.

> Make sound. See its shape. Edit its notes.

## Principles

### 1. Audio and MIDI are the protagonists

Waveforms, playheads, bar/beat grids, clip boundaries, and MIDI notes carry the visual hierarchy. Decorative cards, metrics, and generic feature illustrations do not.

### 2. AI is a tool, not a character

Use clear production verbs:

- Generate Audio
- Insert
- Extract MIDI
- Quantize
- Regenerate
- Render
- Export

Avoid sparkle, magic-wand, brain, and chatbot-first metaphors.

### 3. Human warmth with machine precision

Combine strict grids, timecode, and alignment with a warm coral generation accent and tactile control states.

### 4. Dense but calm

The workspace may be information-dense, but only the current selection and active state should demand attention. Prefer borders, spacing, and hierarchy over blur, glow, and gradients.

### 5. Provenance is part of the editing experience

A generated clip should retain its prompt, model, duration, and relationship to derived MIDI. Audio and MIDI created from the same generation should be visibly linked.

## Color tokens

These are initial tokens, not final accessibility-approved values.

```css
:root {
  --canvas:       #0B0E10;
  --surface-1:    #11161A;
  --surface-2:    #171E23;
  --surface-3:    #20292F;

  --line:         #2A353B;
  --line-strong:  #3B484F;

  --text:         #EEF2EF;
  --text-muted:   #8B9793;
  --text-faint:   #5F6A67;

  --accent-ai:    #FF795F;
  --accent-audio: #E4B05A;
  --accent-midi:  #55D0C0;

  --success:      #86D66D;
  --danger:       #FF646B;
}
```

### Semantic use

| Token | Meaning |
|---|---|
| Coral | AI generation, prompt, generation state |
| Amber | Audio clips and waveform editing |
| Teal | MIDI clips and Piano Roll |
| Green | Ready, saved, successful |
| Red | Error, cancellation, destructive action |
| Neutral scale | Workspace surfaces, text, dividers |

Color should explain the asset type or state. It should not turn the entire interface into a rainbow.

## Typography

- UI: `Pretendard`, `Noto Sans KR`, then system sans fallback
- Timecode and technical values: `IBM Plex Mono`
- Use mono for time, bar/beat, BPM, seed, and technical metadata only
- Keep the type scale compact and readable; do not use oversized marketing headings inside the Studio

## Geometry and surfaces

- Use an 8px spacing rhythm
- Panel radius: 6px
- Control radius: 4–6px
- Modal radius: 8px
- Use visible 1px borders as the primary panel separation
- Use subtle elevation only where it clarifies layering
- Avoid default glassmorphism and giant rounded cards
- Maintain at least 44px touch targets on mobile controls

## Layout posture

The Studio shell should use three functional regions:

```text
Track list  |  Arrangement timeline  |  Inspector / Generate
                           Detail editor below
```

The timeline gets the largest area. The Generate panel expands when invoked and collapses when editing takes priority.

## Asset language

### Audio clip

- Amber-tinted waveform
- Clip name and duration
- Prompt/model provenance in Inspector
- Fade and trim handles
- AI-generated badge only when it adds useful information

### MIDI clip

- Teal note-density preview
- Piano Roll uses teal notes and a high-contrast selected state
- Velocity can be represented by opacity or brightness
- MIDI extracted from audio carries a linked Audio reference

### Linked Audio/MIDI

Show a chain/link relationship rather than duplicating a large amount of metadata:

```text
Audio clip  🔗  MIDI derived from Audio
```

Derived MIDI should be muted by default when first inserted to avoid accidental double playback with the source Audio clip.

## Motion language

Good motion communicates state:

- Playhead follows real playback
- Generation progress grows left-to-right like a waveform
- A clip enters at the playhead position
- MIDI extraction gradually reveals note data
- Inspector transitions stay around 150–200ms

Avoid looping background animation, sparkle effects, and decorative glow pulses. Respect `prefers-reduced-motion`.

## Copy language

Use concise production terminology:

- Generate Audio
- Insert at Playhead
- Extract MIDI
- Fit to Bars
- Regenerate
- Quantize
- Render
- Export

Avoid vague AI copy such as “Unlock,” “Enhance,” “Magic,” or “Transform.”

## Deployment-aware interaction

The product is local-first, but the same Studio can also be hosted in a Colab T4 runtime. The UI should show the current deployment without making hardware the main subject.

```text
Local desktop · GPU
Local desktop · CPU fallback
Colab T4 · HTTPS connected
```

Colab is a deployment target rather than a normal runtime selector inside the local Studio. Its public HTTPS URL and connection state belong to the launch/access flow; the arrangement workspace should remain the same.

The tested T4 configuration has limited headroom after both models are resident. The UI should make serialized work feel intentional:

```text
Variation 1  Ready
Variation 2  Queued
Variation 3  Queued
```

Do not imply unlimited parallel generation. Show clear states for queued, generating, extracting MIDI, ready, and failed jobs. CPU mode should show an honest “may take longer” state rather than a spinner with no explanation. A temporary public HTTPS URL should be visibly treated as remote access, not as proof of authentication.

## First visual milestone

Build and verify these three Studio states before expanding the component library:

1. Empty Studio
2. Studio with a generated Audio clip
3. Studio with linked Audio and MIDI clips

Each state should be understandable without a tutorial and should retain the same timeline-first composition.
