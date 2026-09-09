# NeuronTap product spec — V0.1

## One-sentence product

A private Android media viewer that captures the user's spontaneous reaction-button behavior and turns it into longitudinal personal attraction statistics.

## Core loop

1. Browse local image/video.
2. Press the one reaction button naturally.
3. App records button timing plus context around it.
4. Optionally confirm a completed masturbation session.
5. Analytics distinguishes observed behavior from inferred meaning.
6. Wrapped summarizes long-term patterns.
7. Optional post-hoc tags explain visual / thematic correlates without contaminating spontaneous reaction collection.

## Why gallery-first

Owning the viewer gives exact media identity, dwell, video position, page changes and playback behavior. A system overlay cannot reliably know which third-party item is visually dominant without much more invasive integration.

## Privacy boundary

Base V0.1 has no Internet permission. The media never leaves Android's local content provider. Metadata export anonymizes media URI values.

## Success criteria

The first usable version succeeds if:
- a user can point it at a real large gallery,
- browse images and videos fluidly,
- reaction presses never feel laggy,
- events survive process restarts,
- a confirmed finish produces a plausible primary-media guess,
- Wrapped can surface facts the user did not already remember.
