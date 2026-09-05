const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

assert.match(fs.readFileSync("static/styles.css","utf8"),/\[hidden\]\s*\{\s*display:none\s*!important;\s*\}/,"semantic hidden state must override component display rules");

function node(){return{hidden:true,disabled:false,textContent:"",href:"",open:false,events:{},
  addEventListener(name,handler){this.events[name]=handler;},showModal(){this.open=true;},close(){this.open=false;}};}

function fixture(){
  const ids=["connectTelegram","loginTelegram","loginError","loginDialog","accountBuy","accountRefresh",
    "accountLogout","logoutDialog","logoutError","cancelLogout","confirmLogout","accountNotice"];
  const elements=Object.fromEntries(ids.map(id=>[id,node()])),dom=[];
  let apiImpl=async()=>null,clears=0,applies=0,navigated="",replaced="",toasts=[];
  const context={console,URLSearchParams,setTimeout,clearTimeout,AbortController,STUDENT_OS_ACCOUNT_TIMEOUT_MS:10,
    state:{session:null,telegram:null,student_ai_entitlement:null,lessons:[],deadlines:[]},
    document:{querySelector:selector=>elements[selector.slice(1)],addEventListener:(name,handler)=>{if(name==="DOMContentLoaded")dom.push(handler);}},
    location:{hash:"#settings",search:"",pathname:"/",assign(){},replace:value=>{replaced=value;}},
    sessionStorage:{setItem(){},getItem(){return null;},removeItem(){}},history:{replaceState(){}},
    api:(...args)=>apiImpl(...args),toast:value=>toasts.push(value),renderPhotoAccess(){},refreshEntitlement(){},
    clearPrivateClientState(){clears++;Object.assign(context.state,{session:null,telegram:null,student_ai_entitlement:null,lessons:[],deadlines:[]});},
    applyBootstrapState(value){applies++;Object.assign(context.state,value);context.renderAccountActions();},
    navigate:value=>{navigated=value;}};
  vm.createContext(context);vm.runInContext(fs.readFileSync("static/account.js","utf8"),context);dom[0]();
  return{context,elements,setApi:fn=>{apiImpl=fn;},stats:()=>({clears,applies,navigated,replaced,toasts})};
}

function guest(){return{session:{mode:"guest",user:{role:"user"}},telegram:{identity:null,login_available:true},student_ai_entitlement:null,lessons:[],deadlines:[]};}
function authenticated(role="user"){return{session:{mode:"telegram",user:{role},csrf_token:"fixture"},telegram:{identity:{username:"owner"},login_available:true},student_ai_entitlement:{connected:true}};}

(async()=>{
  const view=fixture(),{context,elements}=view;
  Object.assign(context.state,guest());context.renderAccountActions();
  assert.equal(context.canonicalAuthState(),"guest");assert.equal(elements.connectTelegram.hidden,false);assert.equal(elements.accountLogout.hidden,true);
  for(const role of ["user","admin"]){Object.assign(context.state,authenticated(role));context.renderAccountActions();assert.equal(elements.connectTelegram.hidden,true);assert.equal(elements.accountLogout.hidden,false);}
  for(const value of [{session:null,telegram:null},{session:{mode:"telegram",user:{role:"user"}},telegram:{identity:null}},{session:{mode:"guest",user:{role:"user"}},telegram:{identity:{username:"stale"}}}]){
    Object.assign(context.state,value);context.renderAccountActions();assert.equal(!elements.connectTelegram.hidden&& !elements.accountLogout.hidden,false);
  }
  Object.assign(context.state,authenticated());context.renderAccountActions();Object.assign(context.state,guest());context.renderAccountActions();
  assert.equal(elements.accountLogout.hidden,true,"stale authenticated UI must disappear when canonical state becomes guest");

  const success=fixture();Object.assign(success.context.state,authenticated("admin"));success.elements.logoutDialog.open=true;
  const calls=[];success.setApi(async url=>{calls.push(url);if(url==="/api/auth/guest")return guest().session;if(url==="/api/bootstrap")return guest();return null;});
  await success.elements.confirmLogout.events.click({currentTarget:success.elements.confirmLogout});success.context.renderAccountActions();
  assert.deepEqual(calls,["/api/auth/logout","/api/auth/guest","/api/bootstrap"]);assert.equal(success.elements.logoutDialog.open,false);
  assert.equal(success.context.canonicalAuthState(),"guest");assert.equal(success.elements.accountLogout.hidden,true);assert.equal(success.elements.connectTelegram.hidden,false);
  assert.deepEqual(success.stats(),{clears:1,applies:1,navigated:"today",replaced:"",toasts:["Вы вышли. Доступен гостевой режим."]});

  const duplicate=fixture();Object.assign(duplicate.context.state,authenticated());duplicate.elements.logoutDialog.open=true;let release,logoutCalls=0;
  const pending=new Promise(resolve=>{release=resolve;});duplicate.setApi(async url=>{if(url==="/api/auth/logout"){logoutCalls++;await pending;return null;}if(url==="/api/auth/guest")return guest().session;return guest();});
  const first=duplicate.elements.confirmLogout.events.click({currentTarget:duplicate.elements.confirmLogout});
  const second=duplicate.elements.confirmLogout.events.click({currentTarget:duplicate.elements.confirmLogout});assert.equal(logoutCalls,1);release();await Promise.all([first,second]);assert.equal(logoutCalls,1);

  for(const message of ["Ошибка 500","Сеть недоступна"]){const failure=fixture();Object.assign(failure.context.state,authenticated());failure.elements.logoutDialog.open=true;failure.setApi(async()=>{throw Error(message);});
    await failure.elements.confirmLogout.events.click({currentTarget:failure.elements.confirmLogout});assert.equal(failure.elements.logoutDialog.open,true);assert.equal(failure.elements.confirmLogout.disabled,false);
    assert.equal(failure.elements.logoutError.textContent,message);assert.equal(failure.stats().clears,0);}

  const timeout=fixture();Object.assign(timeout.context.state,authenticated());timeout.elements.logoutDialog.open=true;
  timeout.setApi(async(_url,options)=>new Promise((_,reject)=>options.signal.addEventListener("abort",()=>reject(Error("aborted")))));
  await timeout.elements.confirmLogout.events.click({currentTarget:timeout.elements.confirmLogout});assert.equal(timeout.elements.confirmLogout.disabled,false);
  assert.equal(timeout.elements.logoutError.textContent,"Запрос занял слишком много времени. Повторите.");assert.equal(timeout.stats().clears,0);

  const fallback=fixture();Object.assign(fallback.context.state,authenticated());fallback.elements.logoutDialog.open=true;fallback.setApi(async url=>{if(url==="/api/auth/logout")return null;throw Error("guest bootstrap failed");});
  await fallback.elements.confirmLogout.events.click({currentTarget:fallback.elements.confirmLogout});assert.equal(fallback.elements.logoutDialog.open,false);assert.equal(fallback.stats().clears,1);
  assert.equal(fallback.stats().replaced,"/#today");assert.equal(fallback.elements.confirmLogout.disabled,false);
  console.log("Account runtime: canonical guest/auth UI, logout transition, failures, fallback, stale state and idempotency passed");
})().catch(error=>{console.error(error);process.exitCode=1;});
