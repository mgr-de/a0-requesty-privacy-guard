<p align="center"><img src="assets/icon.svg" alt="Requesty Privacy Guard" width="128" height="128"></p>
# Requesty for Agent Zero 2.13

Version 0.3.0. Privacy policy, credentials and model setup now belong to an explicit agent profile, optionally within a project. Shared model presets and global API keys are never written by setup or deactivation.

## Configure one profile

1. Install the plugin through Agent Zero's plugin installer. Open Requesty → Config.
2. In the native toolbar choose an **Agent profile**. A project can further separate the configuration. All-profiles and project-only saves are rejected. Settings and keys from another project or a legacy global installation are not inherited.
3. Save a Requesty API key for this profile. It is stored under `usr/secrets/requesty/<project-profile-hash>/credentials.json`, outside project repositories and scoped plugin ZIP data. The project/profile identity determines a separate directory; there is no fallback to another profile’s key. It is not added to Agent Zero's shared API Keys list. Files use the host filesystem permissions (atomic writes create mode 0600 on Linux); this is not an encrypted secret vault.
4. Choose region, model-region restriction, no provider retention and no provider training. **Save privacy requirements** keeps the dialog open.
5. Load the authenticated catalog and select Conversation (Main) and Helper (Utility). Excluded models have reasons. Unknown metadata cannot satisfy a required restriction.
6. Run the example test. It sends only a fixed synthetic prompt, at most two requests of 256 output tokens each. API costs may apply. The ticket is valid for ten minutes and bound to this profile, key, policy and model selection.
7. Create the named profile setup, then explicitly **Activate for this profile**. Activation overrides Main and Utility in all chats of that profile and project combination. It does not create or activate a shared preset. Clear existing per-chat model overrides while using the profile setup. Deactivate here to restore the native model selection.

The initial policy is EU router, EU model processing, no provider retention and no provider training. Empty catalogs never relax requirements automatically. Changing profiles clears unsaved credentials, selections and test results, and late responses from the previous profile are ignored. A saved key is not a verified connection; a successful synthetic test is not a privacy audit.

## Data and scope

The plugin pairs with [Local Privacy Guard](https://github.com/mgr-de/a0-local-privacy-guard), which replaces detected details in supported calls and applies local embedding settings to explicitly configured profiles. Detection can miss details and does not cover every external path.

Requesty routing and provider data rules are checked against authenticated catalog metadata, not independently audited. Model aliases and unsupported transport overrides are rejected. A required but unverifiable Requesty organization ZDR setting blocks all requests.

- Provider ZDR is checked using catalog retention/training metadata.
- Requesty's own organization retention is not verified or changed by this plugin.
- Local chats, logs and memory are not deleted by remote ZDR.

While active, a profile uses a separate memory folder identified by its project/profile combination. Existing shared memory is preserved and is not copied automatically. Automatic memory updates append entries without consolidating or replacing old entries. Saved native Memory settings are unchanged. Other profiles keep their own settings and indexes. If Local Privacy Guard is also active, its profile/model-specific memory folder takes precedence. Embedding models remain under native configuration or Local Privacy Guard.

Main and Utility wrappers guard unified calls and LangChain invoke/stream paths. Existing wrapper instances recheck their owning profile at request time and stop after setup changes or deactivation. A separate Vision sidecar is blocked while the setup is active; native Main image support depends on catalog metadata. Catalog caches are separated by router and a hash of the profile key, and return copies.

## Deactivation, removal and migration

**Deactivate profile setup** changes only the selected profile setup's active flag. It preserves credentials, setup and memory. Uninstall hooks no longer delete shared presets or rewrite references in other profiles. Global installation, dependency/provider registration, global toggle and removal of plugin code are Agent Zero administration operations for the entire instance. Use the profile toolbar toggle or profile setup deactivation for a profile-only change.

Agent Zero profiles share one process, filesystem and administrator. Profile ownership prevents accidental configuration and runtime crossover by these plugins; it is not a security sandbox against arbitrary tools, raw third-party model clients or administrators reading/editing files. Use separate instances for mutually untrusted agents.

Legacy global keys, presets, embedding backups and recovery files are preserved rather than automatically migrated or restored. Configure each intended profile explicitly. Legacy `requesty_guarded` presets have no owning setup and fail closed; replace that selection with a native preset or create a profile setup. Native ZIP removal/update may remove scoped override files as part of framework administration, so back up profile plugin data before uninstalling or replacing the plugin.

## Validation

Tests use Agent Zero's actual framework, temporary profile directories, synthetic keys and mocked catalog/model transports. No live paid provider calls were made for this version. They cover two-profile separation, setup/deactivation, expired or profile-crossing tickets, old wrapper objects, scoped Memory settings, native chat-gate status without returning credentials, streaming and failure behavior.

```sh
cd /a0
/opt/venv-a0/bin/python -m pytest usr/plugins/requesty/tests -q
```

See [UI review](docs/UI-REVIEW.md), [profile scope review](docs/PROFILE-SCOPE-REVIEW.md) and [test strategy](docs/TESTSTRATEGY.md).
