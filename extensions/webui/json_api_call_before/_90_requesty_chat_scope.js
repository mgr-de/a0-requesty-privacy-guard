import { store as modelGateStore } from '/components/chat/model-gate-store.js';
import { attachChatContext } from '/plugins/requesty/webui/model-gate-context.js';

export default function requestyChatScope(ctx) {
    const contextId = modelGateStore.pending?.context || globalThis.getContext?.() || '';
    attachChatContext(ctx, contextId);
    const endpoint = String(ctx?.endpoint || '').replace(/^\/?api\//, '/').replace(/^\//, '');
    if (endpoint === 'plugins/_model_config/model_config_get' && ctx.data?.context_id
        && Object.keys(ctx.data).length === 1) ctx.endpoint = 'plugins/requesty/model_status';
}
