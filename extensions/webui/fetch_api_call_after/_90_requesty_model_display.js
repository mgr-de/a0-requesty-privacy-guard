import {callJsonApi} from '/js/api.js';
import {store} from '/plugins/_model_config/webui/model-config-store.js';
import {installModelDisplay,updateModelDisplay} from '/plugins/requesty/webui/model-display.js';

export default async function effectiveModelDisplay(ctx) {
    if (String(ctx?.apiUrl || '')!=='/api/plugins/_model_config/model_override' || !ctx.response?.ok) return;
    let input;
    try {input=JSON.parse(ctx.request?.body || '{}');} catch {return;}
    if ((input.action || 'get')!=='get' || !input.context_id) return;
    const current=()=>globalThis.getContext?.() || '';
    installModelDisplay(store,current);
    if (input.context_id!==current()) return;
    const revision=store._requestyDisplayRevision=(store._requestyDisplayRevision || 0)+1;
    // Clear any older same-chat label while the current identity is resolved.
    store._requestyModelDisplay=null;
    try {
        const native=await ctx.response.clone().json();
        const status=await callJsonApi('/plugins/requesty/model_status',{context_id:input.context_id});
        if (revision!==store._requestyDisplayRevision) return;
        updateModelDisplay(store,input.context_id,current,status,native.override);
    } catch { /* Fall back to the native selector without changing a selection. */ }
}
