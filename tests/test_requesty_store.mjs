import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {test} from 'node:test';

const source = (await readFile(new URL('../webui/requesty-store.js', import.meta.url), 'utf8'))
    .replace(/^import .*;\r?\n/gm, '').replace('export const store =', 'globalThis.store =');
const config = () => ({region:'eu',strict_region:true,no_retention:true,no_training:true,require_requesty_zdr:false});
const model = {id:'example/model',allowed:true,reasons:[]};
function setup(api = async () => ({ok:true,models:[model],ticket:'test-ticket',preset:'Example'})) {
    const calls = [];
    const context = {createStore:(_,s)=>s,callJsonApi:(...args)=>{calls.push(args);return api(...args);},
        toastFrontendSuccess:()=>{},setInterval:()=>1,clearInterval:()=>{},Date,JSON};
    vm.runInNewContext(source, context);
    const store = context.store;
    store.scope = {project_name:"",agent_profile:"agent0"};
    store.hasKey = true; store.keyKnown = true; store.requirementsSaved = true;
    return {store,calls};
}
function deferred() {let resolve; const promise = new Promise(r=>resolve=r); return {promise,resolve};}
test('reopening restores saved model selections and profile setup name', async()=>{
    const {store}=setup(async()=>({ok:true,has_key:true,requirements_saved:true,setup:'Saved setup',
        main:'saved/main',utility:'saved/utility',active:true}));
    await store.onOpen({agentProfileKey:'agent0'});
    assert.equal(store.main,'saved/main');assert.equal(store.utility,'saved/utility');
    assert.equal(store.savedMain,'saved/main');assert.equal(store.savedUtility,'saved/utility');
    assert.equal(store.presetName,'Saved setup');assert.equal(store.active,true);
    assert.equal(store.ticket,'');assert.equal(store.catalogLoaded,false);
    store.cleanup();assert.equal(store.savedMain,'');assert.equal(store.savedUtility,'');
});
async function ready(store,c) {await store.refresh(c);store.main=model.id;store.utility=model.id;await store.testModels(c);}

test('requirements and model changes prevent creation until a new test', async()=>{
    const {store,calls}=setup();const c=config();await ready(store,c);
    assert.ok(store.testCurrent(c));
    c.no_training=false;await store.createPreset(c);assert.equal(calls.length,2);
    c.no_training=true;store.main='different';await store.createPreset(c);assert.equal(calls.length,2);
    store.main=model.id;await store.createPreset(c,true);assert.equal(calls.length,2);
    await store.createPreset(c);assert.equal(calls.length,3);
    assert.equal(store.createdPreset,'Example');assert.match(store.message,/Not activated/);
    assert.match(store.nextStep(c),/Activate Example/);
    assert.equal(store.ticket,'');
});
test('refresh and key replacement invalidate a previous model test', async()=>{
    const {store}=setup();const c=config();await ready(store,c);await store.refresh(c);
    assert.equal(store.ticket,'');await store.testModels(c);store.key='synthetic-key';await store.saveKey();
    assert.equal(store.ticket,'');assert.equal(store.catalogLoaded,false);assert.equal(store.key,'');
});
test('expired tests cannot create and backend failure is persistent', async()=>{
    const {store,calls}=setup();const c=config();await ready(store,c);store.testedAt-=600001;
    await store.createPreset(c);assert.equal(calls.length,2);assert.match(store.nextStep(c),/Run the example/);
    const bad=setup(async()=>({ok:false,error:'Example failure'})).store;await bad.refresh(c);
    assert.equal(bad.error,'Example failure');assert.equal(bad.busy,false);assert.equal(bad.catalogLoaded,false);
});
test('late catalog or validation response cannot bless changed settings', async()=>{
    const pending=deferred();const {store}=setup(()=>pending.promise);const c=config();
    const work=store.refresh(c);c.region='us';pending.resolve({ok:true,models:[model]});await work;
    assert.equal(store.catalogLoaded,false);
    const validation=deferred();const next=setup((url)=>url.endsWith('/validate')?validation.promise:Promise.resolve({ok:true,models:[model]})).store;
    const d=config();await next.refresh(d);next.main=model.id;next.utility=model.id;
    const testing=next.testModels(d);next.utility='different';validation.resolve({ok:true,ticket:'late'});await testing;
    assert.equal(next.ticket,'');
});
test('close and reopen ignore old key status and do not clear a new busy operation', async()=>{
    const old=deferred();const newer=deferred();let n=0;
    const {store}=setup(()=>++n===1?old.promise:newer.promise);
    const first=store.onOpen({agentProfileKey:"agent0"});store.cleanup();const second=store.onOpen({agentProfileKey:"agent0"});
    old.resolve({ok:true,has_key:true});await first;
    assert.equal(store.keyKnown,false);assert.equal(store.busy,true);
    newer.resolve({ok:true,has_key:false});await second;assert.equal(store.hasKey,false);assert.equal(store.busy,false);store.cleanup();
});
test('empty catalog, excluded models, search and blocking ZDR remain distinct', async()=>{
    const {store}=setup(async()=>({ok:true,models:[{...model,allowed:false,reasons:['Location unknown']}]}));
    const c=config();await store.refresh(c);assert.equal(store.filtered().length,0);
    assert.match(store.nextStep(c),/No models/);store.showRejected=true;assert.equal(store.filtered().length,1);
    store.search=' missing ';assert.equal(store.filtered().length,0);
    c.require_requesty_zdr=true;assert.match(store.nextStep(c),/Requests are blocked/);
});
test('inline save uses native settings API without closing and only acknowledges successful writes',async()=>{
    const {store,calls}=setup();const c=config();
    const context={settings:c,hasUnsavedChanges:true,projectName:'',agentProfileKey:'agent0',settingsSnapshotJson:'old'};
    await store.saveRequirements(context);assert.equal(calls[0][0],'plugins');
    assert.equal(calls[0][1].action,'save_config');assert.equal(context.settingsSnapshotJson,JSON.stringify(c));
    assert.equal(context.isSaving,false);assert.match(store.message,/saved/);
    const bad=setup(async()=>({ok:false,error:'Save failed'})).store;context.settingsSnapshotJson='old';
    await bad.saveRequirements(context);assert.equal(context.settingsSnapshotJson,'old');assert.equal(bad.error,'Save failed');
});
test('replacing an active setup makes the new setup inactive and activatable', async()=>{
    const {store}=setup();const c=config();await ready(store,c);store.active=true;
    await store.createPreset(c);
    assert.equal(store.active,false);assert.equal(store.savedMain,model.id);
    assert.equal(store.savedUtility,model.id);assert.match(store.nextStep(c),/Activate Example/);
});

test('scope switching clears credentials and ignores responses from the previous profile', async()=>{
    const pending=deferred();let n=0;
    const {store,calls}=setup(()=>++n===1?pending.promise:Promise.resolve({ok:true,has_key:false}));
    const old=store.onOpen({agentProfileKey:'agent0'});
    store.key='unsaved-secret';
    await store.onOpen({agentProfileKey:'developer'});
    pending.resolve({ok:true,has_key:true,setup:'Alpha',active:true});await old;
    assert.equal(store.key,'');assert.equal(store.hasKey,false);assert.equal(store.active,false);
    assert.equal(store.scope.agent_profile,'developer');
    assert.equal(calls[0][1].agent_profile,'agent0');assert.equal(calls[1][1].agent_profile,'developer');
    store.cleanup();
});

test('all setup API calls carry one explicit profile and no global scope can save', async()=>{
    const {store,calls}=setup();const c=config();await ready(store,c);await store.createPreset(c);
    store.key='synthetic';await store.saveKey();await store.activate();await store.recover();
    for(const [endpoint,payload] of calls) {
        assert.equal(payload.agent_profile,'agent0');assert.equal(payload.project_name,'');
        assert.ok(endpoint.startsWith('plugins/requesty/'));
    }
    const global=setup().store;await global.onOpen({});assert.equal(global.keyKnown,false);
    assert.match(global.nextStep(c),/Choose one agent profile/);
});

test('unchanged defaults can be saved as the first explicit profile policy', async()=>{
    const {store,calls}=setup();store.requirementsSaved=false;
    const c=config();const context={settings:c,hasUnsavedChanges:false,agentProfileKey:'agent0',projectName:''};
    await store.saveRequirements(context);
    assert.equal(calls.length,1);assert.equal(calls[0][0],'plugins');assert.equal(store.requirementsSaved,true);
});
