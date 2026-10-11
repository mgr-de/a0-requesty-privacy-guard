"""Regression tests for the uninstall hook (hook self-deletion bug).

The historical bug: uninstall() deleted the ENTIRE plugin directory
(usr/plugins/requesty), so the framework's delete_plugin() afterwards
failed with FileNotFoundError and skipped cache/module cleanup
(after_plugin_change). These tests prove the hook now only removes
plugin-owned artifacts (the recovery journal) and leaves the plugin
directory intact for the framework to remove.

The real hooks.py is loaded from a relocated copy inside tmp_path so the
test never touches the real plugin directory.
"""

import importlib.util
import shutil
import sys
import types
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOOKS_PATH = PLUGIN_ROOT / "hooks.py"


def _stub_requesty_helpers(monkeypatch):
    """Stub usr.plugins.requesty.helpers.* so the real hooks.py imports cleanly."""
    for name in ("usr", "usr.plugins", "usr.plugins.requesty",
                 "usr.plugins.requesty.helpers"):
        m = types.ModuleType(name)
        m.__path__ = []
        monkeypatch.setitem(sys.modules, name, m)

    cleanup = types.ModuleType("usr.plugins.requesty.helpers.cleanup")
    cleanup.remove_guarded_presets = lambda: {
        "status": "ok", "removed_presets": [],
        "references_repaired": False, "note": "",
    }
    monkeypatch.setitem(sys.modules,
                        "usr.plugins.requesty.helpers.cleanup", cleanup)

    policy = types.ModuleType("usr.plugins.requesty.helpers.policy")

    class PolicyError(ValueError):
        pass

    from dataclasses import dataclass

    @dataclass
    class Policy:
        region: str = "eu"

    policy.PolicyError = PolicyError
    policy.Policy = Policy
    monkeypatch.setitem(sys.modules,
                        "usr.plugins.requesty.helpers.policy", policy)

    catalog = types.ModuleType("usr.plugins.requesty.helpers.catalog")
    catalog.clear = lambda: None
    monkeypatch.setitem(sys.modules,
                        "usr.plugins.requesty.helpers.catalog", catalog)


def _load_hooks(monkeypatch, tmp_path):
    """Load the real hooks.py with the plugin dir relocated into tmp_path."""
    plugin_dir = tmp_path / "usr" / "plugins" / "requesty"
    plugin_dir.mkdir(parents=True)
    shutil.copy(HOOKS_PATH, plugin_dir / "hooks.py")
    _stub_requesty_helpers(monkeypatch)

    spec = importlib.util.spec_from_file_location(
        "rpg_hooks_under_test", plugin_dir / "hooks.py")
    hooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hooks)
    return hooks, plugin_dir


def test_uninstall_keeps_plugin_directory(monkeypatch, tmp_path):
    """The plugin directory and plugin.yaml must survive the uninstall hook;
    the framework deletes them afterwards via delete_plugin()."""
    hooks, plugin_dir = _load_hooks(monkeypatch, tmp_path)
    (plugin_dir / "plugin.yaml").write_text("name: requesty\n", encoding="utf-8")

    result = hooks.uninstall()

    assert result["status"] == "ok"
    assert plugin_dir.exists(), "plugin directory was deleted by the hook"
    assert (plugin_dir / "plugin.yaml").exists(), "plugin.yaml was deleted by the hook"


def test_uninstall_removes_recovery_journal(monkeypatch, tmp_path):
    """The plugin-owned recovery journal is removed by the hook."""
    hooks, plugin_dir = _load_hooks(monkeypatch, tmp_path)
    journal = plugin_dir / "recovery.json"
    journal.write_text('{"state": "applied"}', encoding="utf-8")

    result = hooks.uninstall()

    assert not journal.exists()
    assert result.get("recovery_removed") is True


def test_uninstall_without_journal_is_ok(monkeypatch, tmp_path):
    """No journal present: uninstall still succeeds, no recovery_removed flag."""
    hooks, plugin_dir = _load_hooks(monkeypatch, tmp_path)

    result = hooks.uninstall()

    assert result["status"] == "ok"
    assert "recovery_removed" not in result
    assert plugin_dir.exists()


def test_framework_delete_plugin_flow_succeeds_after_hook(monkeypatch, tmp_path):
    """Simulate the full framework flow: hook, then find_plugin_dir +
    delete_plugin. Must not raise FileNotFoundError."""
    hooks, plugin_dir = _load_hooks(monkeypatch, tmp_path)
    (plugin_dir / "plugin.yaml").write_text("name: requesty\n", encoding="utf-8")

    hooks.uninstall()

    # framework helpers/plugins.py delete_plugin(): find_plugin_dir first
    found = plugin_dir if (plugin_dir / "plugin.yaml").exists() else None
    assert found is not None, (
        "FileNotFoundError: Plugin 'requesty' not found - framework cleanup aborted"
    )
    shutil.rmtree(found)  # framework's files.delete_dir(plugin_dir)
    assert not plugin_dir.exists()


def test_uninstall_reports_cleanup_unavailable(monkeypatch, tmp_path):
    """A failing preset cleanup is reported, never raised, and the plugin
    directory still survives."""
    hooks, plugin_dir = _load_hooks(monkeypatch, tmp_path)
    (plugin_dir / "plugin.yaml").write_text("name: requesty\n", encoding="utf-8")
    sys.modules["usr.plugins.requesty.helpers.cleanup"].remove_guarded_presets = (
        lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    result = hooks.uninstall()

    assert result["status"] == "cleanup_unavailable"
    assert "boom" in result["note"]
    assert plugin_dir.exists()
