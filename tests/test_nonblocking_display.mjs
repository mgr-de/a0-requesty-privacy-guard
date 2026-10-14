import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
const source=(await readFile(new URL('../extensions/webui/fetch_api_call_after/_90_requesty_model_display.js',import.meta.url),'utf8')).replace(/^import .*;$/gm,'').replace('export default function','function');
function setup(){
 let current='a';const pending=[],updates=[];const store={selection:'unchanged'};
 const context={store,getContext:()=>current,callJsonApi:(path,input)=>new Promise((resolve,reject)=>pending.push({path,input,resolve,reject})),installModelDisplay(){},installPresetDisplay(){},toastFrontendError(){},updateModelDisplay:(s,id,get,value)=>{if(id===get())updates.push({kind:'model',id});},updatePresetDisplay:(s,id,get,value)=>{if(id===get())updates.push({kind:'preset',id});}};
 vm.runInNewContext(source+'\nthis.hook=effectiveModelDisplay;',context);
 const ctx=id=>({apiUrl:'/api/plugins/_model_config/model_override',request:{body:JSON.stringify({action:'get',context_id:id})},response:{ok:true,clone:()=>({json:async()=>({override:null})})}});
 return {store,pending,updates,hook:context.hook,ctx,setCurrent:value=>current=value};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('native selector response completes while both display requests remain pending',async()=>{
 const s=setup();let nativeLoaded=false;
 await (async()=>{await s.hook(s.ctx('a'));nativeLoaded=true;})();
 assert.equal(nativeLoaded,true);await tick();assert.equal(s.pending.length,2);assert.deepEqual(s.updates,[]);
 assert.equal(s.store.selection,'unchanged');
 s.pending[1].resolve({});await tick();assert.deepEqual(s.updates,[{kind:'preset',id:'a'}]);
 s.pending[0].resolve({});await tick();assert.equal(s.updates.length,2);
});
test('a late result cannot replace a newer chat display',async()=>{
 const s=setup();s.hook(s.ctx('a'));await tick();s.setCurrent('b');s.hook(s.ctx('b'));await tick();
 s.pending[0].resolve({});s.pending[1].resolve({});await tick();assert.deepEqual(s.updates,[]);
 s.pending[2].resolve({});s.pending[3].resolve({});await tick();assert.equal(s.updates.length,2);assert.ok(s.updates.every(x=>x.id==='b'));
});
test('display failure preserves native selection and produces no unhandled rejection',async()=>{
 const s=setup();s.hook(s.ctx('a'));await tick();s.pending[0].reject(new Error('offline'));s.pending[1].reject(new Error('offline'));await tick();
 assert.equal(s.store.selection,'unchanged');assert.deepEqual(s.updates,[]);
});
