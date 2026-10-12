// Add explanations to native menu entries without renaming or saving presets.
export function installPresetDisplay(store,currentContext,notify) {
    if(store._requestyPresetDisplayInstalled)return;
    store._requestyPresetDisplayInstalled=true;
    const original=store.setPresetOverride;
    store.setPresetOverride=async function(contextId,name){
        const state=this._requestyPresetStatus;
        const item=state?.contextId===contextId ? state.items.find(item=>item.name===name) : null;
        if(item && !item.allowed){notify(item.reasons.join(' '));return null;}
        return await original.call(this,contextId,name);
    };
    const annotate=()=>{
        const state=store._requestyPresetStatus;
        for(const nameElement of document.querySelectorAll('.model-switcher-preset-name')){
            const parent=nameElement.closest('.model-switcher-item');
            const item=state?.contextId===currentContext() ? state.items.find(item=>item.name===nameElement.textContent.trim()) : null;
            let note=parent?.querySelector('.requesty-preset-eligibility');
            if(!item){note?.remove();continue;}
            const text=(item.allowed?'Zulässig':'Nicht zulässig')+(item.allowed?'':' · '+item.reasons.join(' '));
            if(!note){note=document.createElement('div');note.className='requesty-preset-eligibility';note.style.cssText='font-size:.875rem;white-space:normal;overflow-wrap:anywhere;margin-top:.35rem;';parent.append(note);}
            if(note.textContent!==text)note.textContent=text;
        }
    };
    new MutationObserver(annotate).observe(document.body,{childList:true,subtree:true});
    store._requestyAnnotatePresets=annotate;
}

export function updatePresetDisplay(store,contextId,currentContext,result){
    if(contextId!==currentContext())return;
    store._requestyPresetStatus=result?.protected ? {contextId,items:result.presets||[]} : null;
    store._requestyAnnotatePresets?.();
}
