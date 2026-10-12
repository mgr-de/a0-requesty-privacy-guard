"""Scoped native adapters; no service or shared active model changes."""
from dataclasses import asdict
from pathlib import Path
from usr.plugins.requesty.helpers.policy import Policy, PolicyError
from usr.plugins.requesty.helpers import catalog


def install(**kwargs):
    from helpers.providers import reload_providers
    catalog.clear()
    reload_providers()
    from usr.plugins.requesty.helpers.inherited_bridge import manage
    return manage(Path(__file__).parent)


def pre_update(**kwargs):
    catalog.clear()


def uninstall(**kwargs):
    # Remove only owned native adapters; no services or installed dependencies.
    # Profile overrides stop through framework removal. Shared presets and
    # selections are never rewritten; legacy presets require explicit migration.
    catalog.clear()
    from usr.plugins.requesty.helpers.instance import manager
    if manager() is not None:
        raise ValueError('Deactivate Privacy Agent centrally before uninstalling a required component.')
    result = {"status": "ok", "note": "Shared presets, keys and profile data preserved."}
    import importlib.util
    source=Path(__file__).parent/'helpers'/'inherited_bridge.py'
    if source.exists():
        spec=importlib.util.spec_from_file_location('_rpg_inherited_bridge',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        result.update(module.manage(Path(__file__).parent,remove=True))
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
    from usr.plugins.requesty.helpers.instance import manager
    instance=manager()
    if instance is not None:return instance.effective_policy(raw)
    return asdict(Policy.parse(raw)) if raw is not None else asdict(Policy())
