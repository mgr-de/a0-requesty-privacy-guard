from helpers.extension import Extension
from helpers import plugins
from usr.plugins.requesty.helpers import scope

class RequestyProfileSettings(Extension):
    def execute(self, data, **kwargs):
        args = data.get("args", ())
        inputs = args[1] if len(args) > 1 else data.get("kwargs", {}).get("input", {})
        if inputs.get("plugin_name") != "requesty" or not isinstance(data.get("result"), dict):
            return
        project = inputs.get("project_name", "")
        profile = inputs.get("agent_profile", "")
        path = scope.path(scope.scope(project, profile), "config.json") if profile else None
        exists = path is not None and path.exists()
        data["result"] = {"ok":True,
            "data":plugins.get_plugin_config("requesty", project_name=project, agent_profile=profile, caller="ui"),
            "loaded_path":str(path) if exists else "", "loaded_project_name":project if exists else "",
            "loaded_agent_profile":profile if exists else ""}
