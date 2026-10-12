"""Explicit profile ownership; no global credentials or settings fallback."""
import hashlib
import json
import re
from pathlib import Path
from usr.plugins.requesty.helpers.policy import PolicyError

def scope(project="", profile=""):
    for value in (project, profile):
        if not isinstance(value, str) or value in (".", "..") or not re.fullmatch(r"[\w .-]*", value):
            raise PolicyError("Invalid project or agent profile.")
    if not profile:
        raise PolicyError("Choose one agent profile in the settings toolbar first.")
    return (project, profile)

def from_input(value):
    return scope(value.get("project_name", ""), value.get("agent_profile", ""))

def from_agent(agent):
    from helpers import projects
    if agent is None:
        raise PolicyError("Requesty requires an owning agent profile.")
    return scope(projects.get_context_project_name(agent.context) or "", agent.config.profile)

def path(owner, name):
    from helpers import plugins, files
    project, profile = scope(*owner)
    target = Path(plugins.determine_plugin_asset_path("requesty", project, profile, name)).resolve()
    root = Path(files.get_abs_path(files.USER_DIR)).resolve()
    if name == "credentials.json":
        # Keep project keys outside project repositories and ZIP override data.
        identity = hashlib.sha256(json.dumps([project, profile]).encode()).hexdigest()
        target = (root / "secrets" / "requesty" / identity / name).resolve()
    if not target.is_relative_to(root):
        raise PolicyError("Profile storage is outside the user directory.")
    return target

def read(owner, name, default=None):
    target = path(owner, name)
    if not target.exists():
        return default
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except Exception:
        raise PolicyError("Profile storage cannot be read safely.") from None

def key(owner):
    value = read(owner, "credentials.json", {}).get("key", "")
    if not isinstance(value, str) or not value.strip() or value in ("None", "NA"):
        raise PolicyError("Save a Requesty API key for this agent profile first.")
    return value

def memory_subdir(owner):
    return "requesty-profiles/" + hashlib.sha256(json.dumps(owner).encode()).hexdigest()[:32]

def enabled(owner):
    from helpers import plugins
    if not (Path(__file__).parents[1]/'plugin.yaml').is_file():return False
    assets = plugins.find_plugin_assets(".toggle-*", plugin_name="requesty",
        project_name=owner[0], agent_profile=owner[1], only_first=False)
    paths = list(dict.fromkeys(str(Path(item["path"]).parent) for item in assets))
    return plugins.determined_toggle_from_paths(True, reversed(paths))
