import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source=(await readFile(new URL('../webui/preset-display.js',import.meta.url),'utf8')).replace(/export /g,'');
test('ineligible preset rejected without writing or changing its name',async()=>{
 let calls=0,warnings=[];
 const context={document:{body:{},querySelectorAll:()=>[]},MutationObserver:class{observe(){}}};
 vm.createContext(context);vm.runInContext(source,context);
 const store={setPresetOverride:async()=>{calls++;return {ok:true};}};
 context.installPresetDisplay(store,()=> 'one',message=>warnings.push(message));
 context.updatePresetDisplay(store,'one',()=> 'one',{protected:true,presets:[{name:'Default',allowed:false,reasons:['Wrong route']},{name:'Private',allowed:true,reasons:[]}]});
 assert.equal(await store.setPresetOverride('one','Default'),null);assert.equal(calls,0);assert.equal(warnings[0],'Wrong route');
 await store.setPresetOverride('one','Private');assert.equal(calls,1);
 await store.setPresetOverride('other','Default');assert.equal(calls,2);
});
test('stale chat result cannot replace current eligibility',()=>{
 const context={};vm.createContext(context);vm.runInContext(source,context);
 const store={};context.updatePresetDisplay(store,'old',()=> 'new',{protected:true,presets:[]});assert.equal(store._requestyPresetStatus,undefined);
});

test('current protected setup is retained as a separate scoped choice',()=>{
 const context={};vm.createContext(context);vm.runInContext(source,context);
 const store={};const scoped={name:'A0 Privacy · gemeinsam',allowed:true,models:{main:{name:'deepseek-v4.1-flash'}}};
 context.updatePresetDisplay(store,'one',()=> 'one',{protected:true,presets:[],scoped});
 assert.equal(store._requestyPresetStatus.scoped,scoped);
 context.updatePresetDisplay(store,'one',()=> 'one',{protected:false});assert.equal(store._requestyPresetStatus,null);
});
