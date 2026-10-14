# Subagent preset ownership — 14 October 2026

Native subagent calls can run while the parent tool context remains active. The cached-preset check used that ambient parent instead of the agent whose getter constructed the wrapper, rejecting a correctly selected child model with "The preset changed" even after restart.

Validate preset selection against the wrapper's process-local native getter agent reference first. Retain inherited parent credential/policy ownership and the fallback for unbound tool models. An expired bound owner fails closed. This also restores stale-preset checking in Gateway-only calls without an ambient tool context.

Validation: isolated A0 2.14 — 108 Manager, 79 Gateway and 184 Local Guard tests passed (371 total), plus 32 Gateway subtests. Synthetic mocked transports only. Regressions cover same-chat and separate-context subagents with Local Guard on/off, successful mocked native turns, actual preset changes, rebuilt wrappers, absent ambient context and expired ownership. Original parent/child mismatch was reproduced before the correction. Gateway Vision test double now supports weak references like native Agent objects.

No routing or preset changes, no paid calls, Local Guard remains disabled on the user's instances.
