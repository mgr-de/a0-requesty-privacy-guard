# Test Strategy — Requesty Privacy Guard

## Scope

Automated regression coverage for the plugin lifecycle hooks, focused on the
uninstall self-deletion bug (v0.1.2) fixed in v0.1.3, plus the preserved
behavior of the preset cleanup and recovery-journal handling.

## Layers

| Layer | Runner | What it covers | Runs offline |
|---|---|---|---|
| Hook regression | `pytest tests/test_hooks_uninstall.py` | uninstall hook keeps plugin dir, removes only `recovery.json`, full framework delete flow, cleanup-failure reporting | yes |
| Policy unit tests | `pytest tests/test_policy.py` | catalog policy validation (pre-existing) | yes |
| Framework-integrated | `pytest tests/test_*.py` (catalog, configuration, runtime, integration, validation, agent_memory) | provider/preset/recovery behavior against real Agent Zero modules | **no** — needs the A0 runtime (`/opt/venv-a0`, `helpers.*`, `models`) |
| Frontend gate | `node --test tests/test_model_gate_context.mjs` | model-gate context building (pre-existing) | yes |

## Key design decisions

- **`tests/conftest.py` is environment-aware.** When the real Agent Zero
  framework modules (`helpers.files`, `helpers.providers`, `helpers.api`) are
  importable, the conftest does nothing except add the project root to
  `sys.path` — the full pre-existing suite keeps running against the real
  framework. When they are NOT importable (offline development box), it
  installs minimal stubs so the pure hook logic can still be tested.
- **No test mutates the real plugin directory.** `test_hooks_uninstall.py`
  copies the real `hooks.py` into a `tmp_path` plugin tree and loads it with
  `importlib` under a unique module name, with `usr.plugins.requesty.helpers.*`
  stubbed via `monkeypatch`.
- **Defekt→Test mapping** (regression for the fixed bug):

  | Defect | Test |
  |---|---|
  | Hook deleted entire plugin dir → `FileNotFoundError` in `delete_plugin()`, `after_plugin_change()` skipped | `test_uninstall_keeps_plugin_directory`, `test_framework_delete_plugin_flow_succeeds_after_hook` |
  | Recovery journal removal was coupled to the directory deletion | `test_uninstall_removes_recovery_journal`, `test_uninstall_without_journal_is_ok` |
  | Cleanup errors silently swallowed | `test_uninstall_reports_cleanup_unavailable` |

## Running

```bash
# offline (hook regression + policy + node gate)
/opt/venv/bin/python -m pytest tests/test_hooks_uninstall.py tests/test_policy.py -q
node --test tests/test_model_gate_context.mjs

# full suite inside Agent Zero (Docker container, framework on sys.path)
cd /path/to/repo && python -m pytest tests/ -q
```

## Manual integration checklist (not automated)

1. Install the plugin in a real Agent Zero instance, create a `requesty_guarded` preset.
2. Uninstall the plugin via the WebUI → expect: preset removed, references repaired to `Default`, plugin folder gone, **no** `FileNotFoundError` in the log, `after_plugin_change` cleanup runs.
3. Restart the Agent Zero process and verify no stale `requesty_guarded` provider remains registered.
4. With a `recovery.json` present, uninstall → journal gone, no error.
5. Re-install → plugin works, no stale recovery state replayed.

## Known limitations

- The framework-dependent test files (`test_catalog.py`, `test_configuration.py`,
  `test_runtime.py`, `test_integration.py`, `test_validation.py`,
  `test_agent_memory.py`) require the Agent Zero runtime and fail at collection
  on a plain dev box — this is pre-existing and expected, not caused by these
  changes.
- No test exercises a real model call through the guarded provider (needs
  network + credentials).
