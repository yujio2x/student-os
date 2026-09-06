(function(root){
  "use strict";
  function httpsUrl(value,hosts){
    if(typeof value!=="string"||!value||/[\s\\]/.test(value))return "";
    try{const url=new URL(value);return url.protocol==="https:"&&!url.username&&!url.password&&!url.hash&&hosts.includes(url.hostname.toLowerCase())?url.href:"";}catch{return "";}
  }
  function email(value){return typeof value==="string"&&value.length<=254&&/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)?value:"";}
  function link(document,id,labelId,value,kind){
    const hosts=kind==="github"?["github.com","www.github.com"]:["t.me","telegram.me","www.telegram.me"];
    const node=document.querySelector(`#${id}`),label=document.querySelector(`#${labelId}`),safe=kind==="email"?email(value):httpsUrl(value,hosts);
    node.hidden=!safe;node.removeAttribute("href");label.textContent=safe;
    if(safe)node.href=kind==="email"?`mailto:${safe}`:safe;
  }
  function render(project,document){
    const model=project||{};
    document.querySelector("#aboutName").textContent=model.name||"Student OS";
    document.querySelector("#aboutVersion").textContent=model.version||"";
    document.querySelector("#aboutDescription").textContent=model.description||"";
    link(document,"aboutGithub","aboutGithubLabel",model.github_url,"github");
    link(document,"aboutTelegram","aboutTelegramLabel",model.telegram_url,"telegram");
    link(document,"aboutSupport","aboutSupportLabel",model.support_email,"email");
  }
  root.StudentOSAbout={render,httpsUrl,email};
})(globalThis);
