import { store as modelGateStore } from '/components/chat/model-gate-store.js';
import { attachChatContext } from '/plugins/requesty/webui/model-gate-context.js';

export default function requestyChatScope(ctx) {
    const contextId = modelGateStore.pending?.context || globalThis.getContext?.() || '';
    attachChatContext(ctx, contextId);
}
