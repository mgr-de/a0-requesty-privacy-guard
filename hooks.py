"""Lifecycle is non-destructive: no dependencies, services or active model changes."""
from dataclasses import asdict
from pathlib import Path
from usr.plugins.requesty.helpers.policy import Policy, PolicyError
from usr.plugins.requesty.helpers import catalog


def install(**kwargs):
    from helpers.providers import reload_providers
    catalog.clear()
    reload_providers()


def pre_update(**kwargs):
    catalog.clear()


def uninstall(**kwargs):
    # No provider files outside this plugin, no services or installed dependencies.
    # API keys are shared user configuration and are kept. Presets created by this
    # plugin reference the guarded provider and would crash model calls without it,
    # so they are removed and their references repaired to Default here.
    catalog.clear()
    result = {"status": "ok", "cleanup": None}
    try:
        from usr.plugins.requesty.helpers.cleanup import remove_guarded_presets
        result["cleanup"] = remove_guarded_presets()
    except Exception as exc:
        result["status"] = "cleanup_unavailable"
        result["note"] = f"automatic preset cleanup could not run: {exc}"
    # Remove only the plugin-owned recovery journal. The plugin directory
    # itself must stay intact: the framework's delete_plugin() removes the
    # plugin folder after this hook returns and fails with FileNotFoundError
    # (skipping cache/module cleanup) if the folder is already gone.
    try:
        journal = Path(__file__).parent / "recovery.json"
        if journal.exists():
            journal.unlink()
            result["recovery_removed"] = True
    except Exception:
        pass
    return result


def save_plugin_config(settings=None, project_name="", agent_profile="", **kwargs):
    if project_name or agent_profile:
        raise PolicyError("Requesty privacy settings are global in this version.")
    validated = asdict(Policy.parse(settings))
    catalog.clear()
    return validated
