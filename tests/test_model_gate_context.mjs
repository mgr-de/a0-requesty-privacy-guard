import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('../webui/model-gate-context.js', import.meta.url), 'utf8');
const { attachChatContext } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
for (const endpoint of ['/plugins/_model_config/model_config_get', '/api/plugins/_model_config/model_config_get', 'plugins/_model_config/model_config_get']) {
    const request = { endpoint, data: {} };
    attachChatContext(request, 'chat-a');
    assert.deepEqual(request.data, { context_id: 'chat-a' });
}
for (const data of [{context_id:'chat-b'}, {project_name:'project-b'}, {agent_profile:'profile-b'}, null, []]) {
    const request = {endpoint:'/plugins/_model_config/model_config_get', data};
    attachChatContext(request, 'chat-a');
    assert.equal(request.data, data);
}
const unrelated = {endpoint:'/plugins/requesty/catalog', data:{}};
attachChatContext(unrelated,'chat-a');
assert.deepEqual(unrelated.data,{});
const noContext = {endpoint:'/plugins/_model_config/model_config_get', data:{}};
attachChatContext(noContext,'');
assert.deepEqual(noContext.data,{});
console.log('model gate context tests passed');
