<p align="center"><img src="assets/icon.svg" alt="Requesty Privacy Guard" width="128" height="128"></p>
# Requesty for Agent Zero 2.13

Version 0.4.0. Privacy policy, credentials and model setup belong to an explicit agent profile, optionally within a project. Shared model presets and global API keys are never written by setup or deactivation.

An active setup supplies default Main and Utility models. Explicit native presets remain selected and must meet the profile policy: external models use Requesty, while explicitly local Ollama endpoints are allowed. Incompatible selections are rejected without silently replacing them. Main, Utility, Browser and separate Vision calls are checked; image support must be confirmed in the Requesty catalog. Subordinate agents inherit the active root profile's minimum policy during native tool calls. Independent chats retain their own settings.

Ollama is optional, never a prerequisite. The plugin works with approved Requesty models alone. Local text filtering and sentence-transformers embeddings do not need a local chat LLM; optional OCR needs an existing Tesseract installation.

Selections suspended by 0.3.x remain backed up until deactivation; a newer selection is preserved. Reopening settings restores saved setup and model choices. See [the current standardschutz plan](docs/STANDARD-AND-HARDENED-PLAN.md) for boundaries and the optional future hardened mode. The standard plugins do not restrict every browser, form, upload or third-party client.

## Configure one profile

1. Install the plugin through Agent Zero's plugin installer. Open Requesty → Config.
2. In the native toolbar choose an **Agent profile**. A project can further separate the configuration. All-profiles and project-only saves are rejected. Settings and keys from another project or a legacy global installation are not inherited.
3. Save a Requesty API key for this profile. It is stored under `usr/secrets/requesty/<project-profile-hash>/credentials.json`, outside project repositories and scoped plugin ZIP data. The project/profile identity determines a separate directory; there is no fallback to another profile’s key. It is not added to Agent Zero's shared API Keys list. Files use the host filesystem permissions (atomic writes create mode 0600 on Linux); this is not an encrypted secret vault.
4. Choose region, model-region restriction, no provider retention and no provider training. **Save privacy requirements** keeps the dialog open.
5. Load the authenticated catalog and select Conversation (Main) and Helper (Utility). Excluded models have reasons. Unknown metadata cannot satisfy a required restriction.
6. Run the example test. It sends only a fixed synthetic prompt, at most two requests of 256 output tokens each. API costs may apply. The ticket is valid for ten minutes and bound to this profile, key, policy and model selection.
7. Create the named profile setup, then explicitly **Activate for this profile**. Activation supplies Main and Utility defaults in chats of that profile/project combination. Native presets may choose other approved Requesty models or local Ollama models. A direct external provider or conflicting transport is rejected; correct the selection rather than weakening requirements. Activation does not create or activate a shared preset.

The initial policy is EU router, EU model processing, no provider retention and no provider training. Empty catalogs never relax requirements automatically. Changing profiles clears unsaved credentials, selections and test results, and late responses from the previous profile are ignored. A saved key is not a verified connection; a successful synthetic test is not a privacy audit.

## Data and scope

The plugin pairs with [Local Privacy Guard](https://github.com/mgr-de/a0-local-privacy-guard), which replaces detected details in supported calls and applies local embedding settings to explicitly configured profiles. Detection can miss details and does not cover every external path.

Requesty routing and provider data rules are checked against authenticated catalog metadata, not independently audited. Model aliases and unsupported transport overrides are rejected. A required but unverifiable Requesty organization ZDR setting blocks all requests.

- Provider ZDR is checked using catalog retention/training metadata.
- Requesty's own organization retention is not verified or changed by this plugin.
- Local chats, logs and memory are not deleted by remote ZDR.

### Local masking versus hosted PII scanning

Original names and contacts should remain readable in the local browser. Privacy checks must examine what is sent to external services. Local Privacy Guard reduces disclosure by replacing detected values before supported calls; automatic detection does not guarantee complete anonymization.

Requesty's hosted Guardrails receive your request before masking it for the model provider. Fast and model-based ML scanners are available on standard and Enterprise plans. Report sends content unchanged; Mask replaces detected values and restores matching replacements in replies. This plugin does not configure or verify those organization/group Guardrails. [Requesty documentation](https://docs.requesty.ai/features/guardrails)

Zero Data Retention concerns storage; it does not prevent transmission or necessary processing at Requesty. For the goal of keeping original details on the device, local masking is the first layer and hosted scanning can supplement it. Neither higher accuracy nor complete multilingual coverage has been established by our tests. [Requesty privacy policy](https://www.requesty.ai/privacy)

See [the integration test findings](docs/PII-TEST-RESULTS.md) for actual outgoing-request checks, long conversations, reasoning, memory, restart and profile boundaries. The eight live Requesty model calls did not evaluate Requesty's PII scanner.

While active, a profile uses a separate memory folder identified by its project/profile combination. Existing shared memory is preserved and is not copied automatically. Automatic memory updates append entries without consolidating or replacing old entries. Saved native Memory settings are unchanged. Other profiles keep their own settings and indexes. If Local Privacy Guard is also active, its profile/model-specific memory folder takes precedence. Embedding models remain under native configuration or Local Privacy Guard.

Main and Utility wrappers guard unified calls and LangChain invoke/stream paths. Existing wrapper instances recheck their owning profile at request time and stop after deactivation. An alternate model remains usable only when current catalog metadata meets the active policy. Native tool Vision calls use a task-local owner; direct external sidecars are rejected. Catalog caches are separated by router and a hash of the profile key, and return copies. Both plugins must remain installed and enabled for their respective checks; this is not protection against deliberate plugin removal or arbitrary raw model clients.

## Deactivation, removal and migration

**Deactivate profile setup** changes only the selected profile setup's active flag. It preserves credentials, setup and memory. Uninstall hooks no longer delete shared presets or rewrite references in other profiles. Global installation, dependency/provider registration, global toggle and removal of plugin code are Agent Zero administration operations for the entire instance. Use the profile toolbar toggle or profile setup deactivation for a profile-only change.

Agent Zero profiles share one process, filesystem and administrator. Profile ownership prevents accidental configuration and runtime crossover by these plugins; it is not a security sandbox against arbitrary tools, raw third-party model clients or administrators reading/editing files. Use separate instances for mutually untrusted agents.

Legacy global keys, presets, embedding backups and recovery files are preserved rather than automatically migrated or restored. Configure each intended profile explicitly. Legacy `requesty_guarded` presets have no owning setup and fail closed; replace that selection with a native preset or create a profile setup. Native ZIP removal/update may remove scoped override files as part of framework administration, so back up profile plugin data before uninstalling or replacing the plugin.

## Validation

The regression suite uses Agent Zero's actual framework, temporary profile directories, synthetic keys and mocked catalog/model transports. It makes no live paid provider calls. It covers two-profile separation, setup/deactivation, expired or profile-crossing tickets, old wrapper objects, scoped Memory settings, native chat-gate status without returning credentials, streaming and failure behavior. A separate opt-in integration series subsequently made eight authorized live model calls; see the linked findings for its scope and limitations.

```sh
cd /a0
/opt/venv-a0/bin/python -m pytest usr/plugins/requesty/tests -q
```

See [UI review](docs/UI-REVIEW.md), [profile scope review](docs/PROFILE-SCOPE-REVIEW.md) and [test strategy](docs/TESTSTRATEGY.md).

## Current standard-protection validation

See [1.4 / 0.4 test results](docs/STANDARD-TEST-RESULTS.md) for native routes, multilingual sessions, secrets, inherited subordinate policy, images and the partly manual form test. Historical comparison reports describe earlier code. Installation/update hooks create owned native adapters for inherited policies, with ownership journals outside the plugin ZIP; restart Agent Zero after installation/update. Independent other-profile chats are unaffected. Ollama is optional and checked for actual local weights only when selected; Requesty-only use needs no Ollama server. Full mappings contain local original values; malformed/truncated model tokens cannot reliably be restored, and truncated native chat titles use a neutral caption.
