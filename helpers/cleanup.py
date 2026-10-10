"""Cleanup of Requesty-owned model presets.

Removes presets whose model slots reference the guarded provider so an
uninstall can never leave a broken chat/utility model behind. References to
removed presets are repaired to the Default preset through the framework's
own reference-repair logic.

Shared user data is never touched: API keys and presets without the guarded
provider always survive the cleanup.
"""
from __future__ import annotations

GUARDED_PROVIDER = "requesty_guarded"
PRESET_SLOTS = ("chat", "utility", "embedding")


def is_guarded_preset(preset) -> bool:
    """True if any model slot of the preset uses the guarded provider."""
    if not isinstance(preset, dict):
        return False
    for slot in PRESET_SLOTS:
        conf = preset.get(slot)
        if isinstance(conf, dict) and str(conf.get("provider") or "").lower() == GUARDED_PROVIDER:
            return True
    return False


def split_presets(presets):
    """Split a preset collection into (guarded, kept) lists."""
    if not isinstance(presets, list):
        return [], []
    guarded = [p for p in presets if is_guarded_preset(p)]
    kept = [p for p in presets if not is_guarded_preset(p)]
    return guarded, kept


def remove_guarded_presets() -> dict:
    """Remove requesty_guarded presets and repair references to them.

    Called from uninstall() so no broken provider references outlive the
    plugin. Presets without the guarded provider and all API keys are kept.
    """
    summary = {
        "status": "ok",
        "removed_presets": [],
        "references_repaired": False,
        "note": "",
    }

    try:
        from plugins._model_config.helpers import model_config as mc
    except Exception as exc:  # framework helpers unavailable (e.g. test runtime)
        summary["status"] = "skipped"
        summary["note"] = f"model_config unavailable: {exc}"
        return summary

    try:
        presets = mc.get_presets()
    except Exception as exc:
        summary["status"] = "error"
        summary["note"] = f"presets could not be read: {exc}"
        return summary

    guarded, kept = split_presets(presets)
    if not guarded:
        summary["note"] = "no guarded presets found"
        return summary

    try:
        cleaned = mc.validate_presets(kept)
        mc.save_presets(cleaned)
    except Exception as exc:
        summary["status"] = "error"
        summary["note"] = f"cleanup failed, presets left unchanged: {exc}"
        return summary

    summary["removed_presets"] = [
        str(p.get("name") or "") for p in guarded if isinstance(p, dict)
    ]

    try:
        from plugins._model_config.api.model_presets import _rename_preset_references

        default_name = str(mc.DEFAULT_PRESET_NAME)
        renames = [
            {"from": name, "to": default_name}
            for name in summary["removed_presets"]
            if name
        ]
        _rename_preset_references(renames)
        summary["references_repaired"] = True
    except Exception as exc:
        summary["note"] = (
            f"guarded presets removed, but reference repair fell back to Default "
            f"on next load: {exc}"
        )
    return summary
