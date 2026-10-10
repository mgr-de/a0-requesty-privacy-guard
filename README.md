# Requesty for Agent Zero 2.13

Version 0.1.1, tested on Agent Zero v2.13 in an isolated Docker instance. Test your own model choices before production use.

0.1.1 fixes Agent Zero 2.13's chat model gate checking global credentials instead of a per-chat preset. A native JSON API extension attaches the current/pending chat context to the empty model-status request. Explicit scopes and global preset editor requests are preserved; backend key checks and all Requesty runtime privacy guards remain active.

## Install and configure

1. Install the ZIP through Settings → Plugins → Install → From ZIP.
2. Open Requesty → Config. Save a separate Requesty test key. The key is stored by Agent Zero's API-key manager as `API_KEY_REQUESTY_GUARDED`, outside presets and plugin configuration.
3. Choose the router region, model-region restriction, provider zero retention and exclusion of training. Save through the normal plugin Settings button.
4. Load the authenticated model catalog. Rejected models have explicit reasons; unknown metadata cannot satisfy a mandatory restriction.
5. Select Main and Utility models. Run the synthetic model tests. They send a fixed artificial prompt, no chats or Memory, with at most two requests of 256 output tokens each. API costs may apply.
6. Create a separate named preset. It is not activated automatically. Test it in a separate chat before selecting it globally.

The initial policy is EU router, EU model processing, no provider retention and no provider training. The supported region mapping is deliberately limited; unfamiliar provider location values are rejected until verified.

## ZDR has three distinct scopes

- Model provider: checked against `data_retention`, `data_retention_days`, and `data_used_for_training` from the Requesty catalog.
- Requesty organization: the documented organization API does not currently expose a verified ZDR flag. Enabling the requirement for verified Requesty ZDR blocks requests. This plugin does not enable permanent organization ZDR or misrepresent provider metadata as organization verification.
- Agent Zero: local chats, Memory, Knowledge, logs and caches remain under Agent Zero's own configuration. Remote ZDR does not delete local data.

Requesty catalog metadata is a provider assertion, not an independent audit. End-to-end regional enforcement also requires appropriate Requesty organization/model approvals. Routing policy aliases are rejected by this version.

## Memory protection

Preset creation copies the complete effective embedding configuration unchanged. It does not register a Requesty embedding provider or migrate existing indexes. A separate Vision sidecar is disabled in the newly created preset; Main native vision is taken from the catalog. Existing presets are preserved.

Utility calls can contain recalled Memory or conversation content, even when embeddings are local. The guards cover Main and Utility calls and Requesty Vision `unified_call` requests. Main/Utility wrappers returned by Agent also guard LangChain invoke and streaming calls. Arbitrary third-party code that calls raw LiteLLM or constructs an independent unguarded LangChain wrapper is outside this plugin's boundary.

Catalog snapshots are authenticated, separated by key and router, valid for at most 60 seconds, and refreshed for UI validation. No anonymous or generic registry fallback is used for policy decisions. Retries retain the checked endpoint/model parameters. Settings/key changes invalidate pending validation.

## Recovery and removal

The recovery button undoes the latest preset creation only while newer preset edits would not be overwritten. The native preset API repairs references when the created preset is removed. If another edit happened, select the previous preset manually instead of overwriting the newer collection.

Before disabling or uninstalling, select another existing preset for all affected chats, projects and profiles. Disabled plugin presets use the deliberately nonstandard `requesty_guarded` provider ID and are intended to fail closed rather than fall through to a built-in Requesty route. Settings remain accessible without successful model inference.

Installation/update hooks reload provider metadata; no packages or background services are installed. Uninstall preserves shared API keys and presets rather than deleting unrelated configuration. Plugin-local settings and recovery data are removed with the plugin directory by Agent Zero.

Back up the instance before production use while all writers are stopped. Include project-scoped Memory in addition to `usr/memory`, along with settings, model presets and required secrets. Restore into a separate volume and verify before applying changes to the original instance.

## Development verification

Use Agent Zero's framework interpreter (`/opt/venv-a0/bin/python` in the tested image):

```sh
cd /a0
/opt/venv-a0/bin/python -m unittest discover -s usr/plugins/requesty/tests -v
```

Tests use synthetic keys, mocked network/LLM results and temporary FAISS directories. They cover automatic recall, fragment/solution extraction, consolidation error behavior, index persistence and restore. Live tests were run separately with synthetic prompts, native Agent streaming/tool responses, Utility and automatic recall. They do not establish reliability of every catalog model or arbitrary third-party plugins.

Agent Zero can insert the original new text locally when consolidation analysis fails (its SKIP fallback), while logging a warning. V1 therefore overrides effective automatic Memory settings for agents using Requesty Utility: consolidation is disabled and automatic replacement threshold is zero. Guarded fragment/solution extraction appends entries instead, preserving existing documents. The saved Memory settings are not changed; other Utility providers retain their settings. Manual Memory operations and third-party code calling the consolidator directly retain native behavior. Profiles retain native Memory scope rules; selecting a model preset does not create a new isolated Memory scope.

The creation journal and preset file are separate atomic writes, not one transaction. Native settings/preset editors do not share a transaction lock with this plugin. Avoid concurrent configuration editing during creation/recovery. Changed or unreadable presets stop automatic recovery instead of overwriting newer edits. The recovery journal is plugin-local; uninstall removes it. ZIP updates require backing up configuration, uninstalling and installing the replacement through Agent Zero's installer.

## Version 0.1.2

All plugin settings labels, help text, and frontend notifications are in English. Configuration keys and runtime privacy, region, and memory behavior are unchanged.
