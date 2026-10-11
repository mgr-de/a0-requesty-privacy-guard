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
    # Profile overrides stop through framework removal. Shared presets and
    # selections are never rewritten; legacy presets require explicit migration.
    catalog.clear()
    result = {"status": "ok", "note": "Shared presets, keys and profile data preserved."}
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
    from usr.plugins.requesty.helpers.scope import scope
    scope(project_name, agent_profile)
    validated = asdict(Policy.parse(settings))
    catalog.clear()
    return validated


def get_plugin_config(default=None, project_name="", agent_profile="", **kwargs):
    # Do not inherit a legacy global policy into an unconfigured profile.
    if not agent_profile:
        return asdict(Policy())
    from usr.plugins.requesty.helpers import scope
    raw = scope.read(scope.scope(project_name or "", agent_profile), "config.json")
    return asdict(Policy.parse(raw)) if raw is not None else asdict(Policy())
