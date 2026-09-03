const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const code=fs.readFileSync('static/pwa.js','utf8');
async function fixture(standalone=false){
  const events={},dom={},clicks={};let button,registered,removed=0;
  const old={scope:'http://localhost/static/',active:{scriptURL:'http://localhost/static/sw.js'},unregister:async()=>removed++};
  const foreign={scope:'http://localhost/other/',active:{scriptURL:'http://localhost/other/sw.js'},unregister:()=>{throw Error('foreign worker');}};
  const context={window:{addEventListener:(name,fn)=>events[name]=fn},
    document:{addEventListener:(name,fn)=>dom[name]=fn,querySelector:()=>({closest:()=>({append:value=>button=value})}),
      createElement:()=>({hidden:true,disabled:false,addEventListener:(name,fn)=>clicks[name]=fn})},
    navigator:{serviceWorker:{register:async(...args)=>registered=args,getRegistrations:async()=>[old,foreign]}},
    location:{origin:'http://localhost'},matchMedia:()=>({matches:standalone})};
  vm.runInNewContext(code,context);dom.DOMContentLoaded();
  assert.equal(button.hidden,true);await events.load();
  assert.equal(registered[0],'/sw.js');assert.equal(registered[1].scope,'/');assert.equal(removed,1);
  return {events,button,clicks};
}
(async()=>{
  const {events,button,clicks}=await fixture();let prompts=0,prevented=0,resolve;
  events.beforeinstallprompt({preventDefault:()=>prevented++,prompt:async()=>prompts++,userChoice:new Promise(r=>resolve=r)});
  assert.equal(button.hidden,false);assert.equal(prevented,1);
  const first=clicks.click();await clicks.click();assert.equal(prompts,1);
  resolve({outcome:'dismissed'});await first;assert.equal(button.hidden,true);assert.equal(button.disabled,false);
  events.beforeinstallprompt({preventDefault(){},prompt:async()=>{},userChoice:Promise.resolve({outcome:'accepted'})});
  events.appinstalled();assert.equal(button.hidden,true);
  const installed=await fixture(true);installed.events.beforeinstallprompt({preventDefault(){}});assert.equal(installed.button.hidden,true);
  console.log('PWA runtime: eligibility, double click, dismissal, installed, scope and migration passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
