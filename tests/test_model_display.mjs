import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../webui/model-display.js',import.meta.url),'utf8');
const {installModelDisplay,updateModelDisplay}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
let selected='protected';
const preset={name:'Default',chat:{name:'gpt-6.1-sol'}};
const store={switcherPresets:[preset],switcherOverride:null,getSwitcherLabel:()=> 'Default gpt-6.1-sol',getActiveModels:()=>({main:preset.chat})};
const current=()=>selected;
const status={requesty_active:true,effective_models:{main:{provider:'requesty_guarded',name:'tensorx/deepseek-v4.1-flash'},utility:{name:'synthetic-helper'}}};
installModelDisplay(store,current);installModelDisplay(store,current);
updateModelDisplay(store,'protected',current,status,null);
assert.equal(store.getSwitcherLabel(),'Requesty deepseek-v4.1-flash');
assert.equal(store.getActiveModels().main.name,'tensorx/deepseek-v4.1-flash');
assert.equal(store.switcherOverride,null);
assert.deepEqual(store.switcherPresets,[preset]);
selected='independent';
assert.equal(store.getSwitcherLabel(),'Default gpt-6.1-sol');
updateModelDisplay(store,'protected',current,status,null);
assert.equal(store.getSwitcherLabel(),'Default gpt-6.1-sol');
selected='protected';
updateModelDisplay(store,'protected',current,status,{preset_name:'Approved'});
assert.equal(store.getSwitcherLabel(),'Approved deepseek-v4.1-flash');
updateModelDisplay(store,'protected',current,{},null);
assert.equal(store.getSwitcherLabel(),'Default gpt-6.1-sol');
console.log('effective model display preserves presets and other chats');

// Native migration labels follow the actual selected preset.
updateModelDisplay(store,'protected',current,{...status,native_presets:true,selected_preset:'Efficiency'},null);
assert.equal(store.getSwitcherLabel(),'Efficiency deepseek-v4.1-flash');
