# Preset display performance — 14 October 2026

The chat switcher waits for the fetch-after hook to finish. Our display enrichment awaited Gateway model_status and then preset eligibility, delaying native model selection display by both extra requests. On the loaded test instance these requests took 5.321 and 7.608 seconds, versus 0.333 seconds for the native override read.

Run display-only enrichment in the background and issue the two independent read requests in parallel. The native response can complete immediately. Preserve revision/context checks, native fallback and independent server validation before preset changes and model sends. No backend, route, key or policy change; Local Guard stays off.

Validation: 22 Gateway Node tests passed, including deferred-response tests showing that the native selector proceeds while enrichment is pending, late replies cannot replace another chat, and failures retain the native selection without unhandled rejection. No model calls.

These UI request durations were observed under concurrent researcher load. They include server/network/contention time and are not isolated CPU measurements. Separate warm Gateway validation samples took 71–75 ms; repeated integrity checks account for most measured local validation overhead. The fix removes display waiting, not that backend work or the duration of autonomous research.
