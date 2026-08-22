# Health ingest via iOS Shortcut

A stable, always-on way to get **weight, steps, and sleep** off the phone and
into the app — without depending on Health Auto Export's background pushes.

## Why this exists

The H4 diagnosis (`docs/APPLE_HEALTH_DIAGNOSIS.md`) found the health pipeline
was untrustworthy mostly because of *delivery*, not math: HAE's scheduled
pushes only fire reliably when its app is open, and quick-tunnel URLs rot. An
iOS **Shortcut** driven by a Personal Automation runs on the phone's own
schedule and can post straight at the **production Railway URL** (stable,
always on). It reuses the exact same validated ingest pipeline as the
`export.xml` history backfill — unit conversion, wake-date sleep bucketing,
multi-source dedup, and manual-precedence — so what it writes obeys the same
rules a backfill does.

This is additive. HAE and the `export.zip` backfill still work unchanged;
nutrition/micronutrients still arrive through those. The Shortcut just covers
the three core numbers reliably.

## Endpoint spec

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `https://<your-app>/api/ingest/health/shortcut` |
| **Auth header** | `Authorization: Bearer <APP_TOKEN>` |
| **Content-Type** | `application/json` |

Use your **production** origin as `<your-app>` (the same host the installed PWA
talks to), and the **same token** you set in Settings → API token (it must match
the backend's `APP_TOKEN`). The Settings → *Apple Health sync* card shows your
exact URL and header, pre-filled and copyable.

### Request body

All three sections are optional — post only what you have. A section may be a
single object or an array of them.

```json
{
  "weight": [
    { "date": "2026-07-18T07:20:00-03:00", "kg": 82.4 }
  ],
  "steps": [
    { "date": "2026-07-18", "count": 11205 }
  ],
  "sleep": [
    {
      "date": "2026-07-18",
      "asleep_minutes": 427,
      "in_bed_minutes": 465,
      "deep_minutes": 68,
      "rem_minutes": 95,
      "core_minutes": 264
    }
  ]
}
```

**Fields** (accepted spellings in parentheses — pick whichever your Shortcut
produces most easily):

- **`date`** — required on every item.
  - Weight is bucketed by this timestamp's **calendar date**; the *latest*
    reading of a day wins.
  - Steps and sleep take the **date** portion only.
  - Sleep's `date` is the **wake-up morning** (run the automation in the
    morning and use "today").
  - Accepts a bare date (`2026-07-18`) or an ISO 8601 timestamp with offset
    (`2026-07-18T07:20:00-03:00`). Values like `82,5` (comma decimal) are
    understood too.
- **weight** — value in `kg` (or `value` / `weight_kg` / `qty`), optional
  `unit` of `kg` (default), `lb`, or `g`.
- **steps** — `count` (or `steps` / `value` / `qty`).
- **sleep** — `asleep_minutes` and/or `in_bed_minutes`, plus optional
  `deep_minutes` / `rem_minutes` / `core_minutes` (`_minutes` suffix optional,
  camelCase accepted).

### Response — the import report

`200 OK` with a report of exactly what landed. This is the trust gate: check
it (or the Settings "synced …" badge) to confirm a push worked.

```json
{
  "status": "ok",
  "records_parsed": 3,
  "days": { "weight": 1, "steps": 1, "sleep": 1, "nutrition": 0 },
  "rows_created": 3,
  "date_range": { "from": "2026-07-18", "to": "2026-07-18" },
  "sections_handled": ["sleep", "steps", "weight"],
  "ignored": [],
  "warnings": []
}
```

- `rows_created` counts **new** days. A repost of the same data returns `0` —
  the upserts are idempotent.
- A day you edited by hand in the app is **never** overwritten (source
  precedence: `manual` beats `apple_health`).
- Bad items are skipped with a note in `warnings` rather than failing the
  whole push; unknown top-level keys are echoed in `ignored`.

## Building the Shortcut

1. **Shortcuts app → new Shortcut.** Add, per metric you want:
   - *Get Health Sample* → Body Mass → most recent → into a variable.
   - *Get Health Sample* → Steps → today's total.
   - *Get Health Sample* → Sleep → last night (asleep + in-bed minutes).
2. *Text* / *Dictionary* actions to assemble the JSON body above from those
   variables (today's date via the *Current Date* → *Format Date* → `yyyy-MM-dd`).
3. *Get Contents of URL*:
   - URL = your endpoint (above), Method = **POST**.
   - Headers: `Authorization` = `Bearer <APP_TOKEN>`, `Content-Type` =
     `application/json`.
   - Request Body = **JSON** (or the assembled text).
4. Optionally *Show Result* to eyeball the report while testing.
5. **Automation:** Personal Automations → new → *Time of Day* (e.g. 08:00),
   run the Shortcut, and turn **off** "Ask Before Running".

### Recommendation (from the H4 diagnosis)

Post a **rolling last few days**, one item per day per metric, not just
"today". Because the upserts are idempotent and `apple_health` overwrites
`apple_health`, every run then self-heals any day a previous run missed —
which is what made HAE fragile.

## Testing it

```bash
curl -X POST https://<your-app>/api/ingest/health/shortcut \
  -H "Authorization: Bearer <APP_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"weight":[{"date":"2026-07-18","kg":82.4}],
       "steps":[{"date":"2026-07-18","count":11205}],
       "sleep":[{"date":"2026-07-18","asleep_minutes":427,"in_bed_minutes":465}]}'
```

The response report should show the rows, and the values then appear in the
app (dashboard weight chart, `GET /api/health/weight|steps|sleep`) and the
Settings "synced …" badge updates.
