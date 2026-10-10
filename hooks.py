"""Lifecycle is non-destructive: no dependencies, services or active model changes."""
from dataclasses import asdict
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
    # Keep presets and API keys: deleting shared user configuration here would be unsafe.
    catalog.clear()


def save_plugin_config(settings=None, project_name="", agent_profile="", **kwargs):
    if project_name or agent_profile:
        raise PolicyError("Requesty privacy settings are global in this version.")
    validated = asdict(Policy.parse(settings))
    catalog.clear()
    return validated
