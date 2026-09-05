(function initializeStudentOSTheme(root){
  const key="student-os-device-theme",allowed=new Set(["light","dark","system"]);
  function read(){try{const value=root.localStorage.getItem(key);return allowed.has(value)?value:null;}catch{return null;}}
  function resolve(accountTheme){return read()||(allowed.has(accountTheme)?accountTheme:"light");}
  function apply(value,{persist=true}={}){
    const theme=allowed.has(value)?value:"light";
    root.document.documentElement.dataset.theme=theme;
    const dark=theme==="dark"||(theme==="system"&&root.matchMedia?.("(prefers-color-scheme: dark)").matches);
    const meta=root.document.querySelector('meta[name="theme-color"]');
    if(meta)meta.content=dark?"#111115":"#f4f5f7";
    if(persist)try{root.localStorage.setItem(key,theme);}catch{}
    return theme;
  }
  root.StudentOSTheme=Object.freeze({key,read,resolve,apply});
  const stored=read();
  if(stored)apply(stored,{persist:false});
})(globalThis);
