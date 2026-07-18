# Audio cues

These four MP3s are the app's sound layer, played by `src/audio.js`:

| File | Event | Character |
|---|---|---|
| `app-open.mp3` | App opened (first unlock on iOS) | gentle single note |
| `tap.mp3` | Button tap | very short, subtle blip |
| `workout-complete.mp3` | Workout finished | celebratory rising chime |
| `rank-up.mp3` | A body-part rank promotion | bigger rising fanfare |

> ⚠️ **Placeholders.** These are synthesized tones generated to make the audio
> pipeline load and be testable. Drop your real sound design in at the same
> filenames (mono/stereo MP3, keep them short — tap especially should be well
> under ~150 ms so there's no audible lag). No code change needed; the service
> imports these paths directly and Vite hashes them into the build.
