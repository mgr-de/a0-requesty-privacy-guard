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
        for(const panel of document.querySelectorAll('#section-models-summary, .agent-model-preset')){
            let note=panel.querySelector('.requesty-instance-preset-note');
            if(!state?.instanceActive){note?.remove();continue;}
            if(!note){note=document.createElement('p');note.className='requesty-instance-preset-note';panel.append(note);}
            const text=state.nativePresets ? 'Privacy Agent aktiv: Dieses native Preset bestimmt die Modelle. Main, Utility und Vision verwenden Requesty; Embeddings bleiben lokal. Modelle können hier bei aktivem Schutz geändert werden.' : 'Privacy Agent aktiv: Die effektiven Modelle kommen aus der gemeinsamen Privacy-Einrichtung oder einem zulässigen Profilsetup. Die globalen Presets allein bestimmen diese Route nicht. Im Chat-Menü steht die geprüfte Privacy-Auswahl; unzulässige Chat-Presets bleiben gesperrt.';
            if(note.textContent!==text)note.textContent=text;
        }
        for(const menu of document.querySelectorAll('.model-switcher-dropdown')){
            let choice=menu.querySelector('.requesty-scoped-choice');
            const scoped=state?.contextId===currentContext() ? state.scoped : null;
            if(!scoped){choice?.remove();continue;}
            if(!choice){
                choice=document.createElement('button');choice.type='button';
                choice.className='model-switcher-item requesty-scoped-choice';
                choice.style.cssText='width:100%;text-align:left;color:inherit;font:inherit;border:0;';
                const title=document.createElement('strong');title.className='requesty-scoped-title';choice.append(title);
                const detail=document.createElement('div');detail.className='model-switcher-preset-models requesty-scoped-detail';
                detail.style.whiteSpace='pre-line';choice.append(detail);
                choice.addEventListener('click',async()=>{
                    const live=store._requestyPresetStatus;
                    if(live?.contextId!==currentContext() || !live.scoped?.allowed)return;
                    if(!await store.clearOverrideSwitch(live.contextId))notify('Privacy-Einrichtung konnte nicht ausgewählt werden. Bitte erneut versuchen.');
                    annotate();
                });
                menu.prepend(choice);
            }
            const active=!store.switcherOverride;
            choice.disabled=!scoped.allowed;
            choice.classList.toggle('active',active);
            const label=scoped.name+(active?' · aktiv':' · verwenden');
            const title=choice.querySelector('.requesty-scoped-title');if(title.textContent!==label)title.textContent=label;
            const models=scoped.models || {};
            const text=scoped.allowed ? ['Zulässig · gespeicherte Privacy-Einrichtung',...Object.entries(models).map(([slot,m])=>slot+': '+(m.name || 'unbekannt'))].join('\n') : scoped.reasons.join(' ');
            const detail=choice.querySelector('.requesty-scoped-detail');if(detail.textContent!==text)detail.textContent=text;
        }
        for(const nameElement of document.querySelectorAll('.model-switcher-preset-name')){
            const parent=nameElement.closest('.model-switcher-item');
            const item=state?.contextId===currentContext() ? state.items.find(item=>item.name===nameElement.textContent.trim()) : null;
            let note=parent?.querySelector('.requesty-preset-eligibility');
            if(!item){note?.remove();continue;}
            if(state.scoped && !store.switcherOverride)parent?.classList.remove('active');
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
    store._requestyPresetStatus=result?.protected ? {contextId,items:result.presets||[],scoped:result.scoped||null,instanceActive:!!result.instance_protection,nativePresets:!!result.native_presets} : null;
    store._requestyAnnotatePresets?.();
}
