"""Test bootstrap for Requesty Privacy Guard.

Makes the production-like directory layout importable (so that
`usr.plugins.requesty...` resolves, mirroring how Agent Zero adds the
parent of `usr/` to sys.path) and, only when the real Agent Zero framework
modules are NOT importable (offline development), stubs the framework
modules that hooks.py touches, so hook logic can be tested standalone.

In a real Agent Zero environment this conftest is a no-op apart from the
sys.path entry, and the full existing test suite keeps using the real
framework modules.
"""

import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _framework_available() -> bool:
    try:
        import helpers.files  # noqa: F401
        import helpers.providers  # noqa: F401
        import helpers.api  # noqa: F401
        return True
    except Exception:
        return False


def _install_framework_stubs() -> None:
    helpers = types.ModuleType("helpers")
    helpers.__path__ = []

    files_mod = types.ModuleType("helpers.files")
    files_mod.get_abs_path = lambda *p: str(Path(*p))
    files_mod.exists = lambda *p: Path(*p).exists()
    files_mod.delete_dir = lambda *p: None
    helpers.files = files_mod

    providers_mod = types.ModuleType("helpers.providers")
    providers_mod.reload_providers = lambda: None
    helpers.providers = providers_mod

    helpers.extension = types.ModuleType("helpers.extension")

    plugins_mod = types.ModuleType("helpers.plugins")
    plugins_mod.get_plugin_config = lambda *a, **k: {}
    plugins_mod.get_toggle_state = lambda *a, **k: "enabled"
    helpers.plugins = plugins_mod

    api_mod = types.ModuleType("helpers.api")

    class ApiHandler:
        def __init__(self, *a, **k):
            pass

    api_mod.ApiHandler = ApiHandler
    helpers.api = api_mod

    sys.modules.setdefault("helpers", helpers)
    sys.modules.setdefault("helpers.files", files_mod)
    sys.modules.setdefault("helpers.providers", providers_mod)
    sys.modules.setdefault("helpers.extension", helpers.extension)
    sys.modules.setdefault("helpers.plugins", plugins_mod)
    sys.modules.setdefault("helpers.api", api_mod)


if not _framework_available():
    _install_framework_stubs()
