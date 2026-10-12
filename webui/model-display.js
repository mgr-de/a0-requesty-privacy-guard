// Overlay effective identities only in this chat's display, preserving preset selections.
export function installModelDisplay(store, currentContext) {
    if (store._requestyDisplayInstalled) return;
    store._requestyDisplayInstalled=true;
    const label=store.getSwitcherLabel;
    const models=store.getActiveModels;
    const active=()=>store._requestyModelDisplay?.contextId===currentContext() ? store._requestyModelDisplay : null;
    store.getSwitcherLabel=function() {return active()?.label || label.call(this);};
    store.getActiveModels=function() {return active()?.models || models.call(this);};
}

export function updateModelDisplay(store, contextId, currentContext, status, override) {
    if (contextId!==currentContext()) return;
    if(status?.model_configured===false && status?.policy_error){
        store._requestyModelDisplay={contextId,label:'Privacy: Modellaufruf blockiert',models:status.effective_models||{}};
        return;
    }
    if (!status?.requesty_active) {store._requestyModelDisplay=null;return;}
    const main=status.effective_models?.main?.name || '';
    const leaf=main.slice(main.lastIndexOf('/')+1);
    const prefix=override?.preset_name || (override ? 'Custom' : status.native_presets ? status.selected_preset || 'Default' : 'Requesty');
    store._requestyModelDisplay={contextId,label:leaf ? `${prefix} ${leaf}` : prefix,models:status.effective_models};
}
