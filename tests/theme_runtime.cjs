const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

const code=fs.readFileSync("static/theme.js","utf8");

function fixture(initial=null,darkSystem=false){
  const values=new Map(initial?[['student-os-device-theme',initial]]:[]),meta={content:"#17171b"};
  const context={document:{documentElement:{dataset:{}},querySelector:selector=>selector==='meta[name="theme-color"]'?meta:null},
    localStorage:{getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)},matchMedia:()=>({matches:darkSystem})};
  context.globalThis=context;vm.runInNewContext(code,context);
  return{context,values,meta};
}

for(const theme of ["light","dark","system"]){
  const view=fixture(theme,theme==="system");
  assert.equal(view.context.document.documentElement.dataset.theme,theme,`${theme} must apply before the app bootstrap`);
  assert.equal(view.context.StudentOSTheme.read(),theme);
}

const ownerDark=fixture("dark");
ownerDark.context.StudentOSTheme.apply("dark");
assert.equal(ownerDark.context.StudentOSTheme.read(),"dark","owner dark must remain the device preference through logout");
assert.equal(ownerDark.context.StudentOSTheme.resolve("light"),"dark","guest bootstrap must not replace owner dark during logout");
assert.equal(ownerDark.context.document.documentElement.dataset.theme,"dark");

const ownerLight=fixture("light");ownerLight.context.StudentOSTheme.apply("light");assert.equal(ownerLight.context.StudentOSTheme.read(),"light");assert.equal(ownerLight.context.StudentOSTheme.resolve("dark"),"light");
const ownerSystem=fixture("system",true);ownerSystem.context.StudentOSTheme.apply("system");assert.equal(ownerSystem.context.StudentOSTheme.read(),"system");assert.equal(ownerSystem.context.StudentOSTheme.resolve("light"),"system");assert.equal(ownerSystem.meta.content,"#111115");

const reopened=fixture("dark");assert.equal(reopened.context.document.documentElement.dataset.theme,"dark","PWA/browser reopen must apply the stored theme before render");
const unrelated=fixture();assert.equal(unrelated.context.StudentOSTheme.read(),null,"a fresh browser store must not inherit another device theme");assert.equal(unrelated.context.document.documentElement.dataset.theme,undefined);
const invalid=fixture("owner-admin");assert.equal(invalid.context.StudentOSTheme.read(),null,"theme storage cannot carry owner/admin state");assert.equal(invalid.context.document.documentElement.dataset.theme,undefined);

console.log("Theme runtime: dark, light, system, reload, device isolation and auth-state separation passed");
