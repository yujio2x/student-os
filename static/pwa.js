// Installation is offered only when the browser reports eligibility.
(()=>{
  let pendingInstall=null,button=null;
  const standalone=()=>matchMedia("(display-mode: standalone)").matches||navigator.standalone===true;
  const render=()=>{if(button)button.hidden=!pendingInstall||standalone();};
  window.addEventListener("beforeinstallprompt",event=>{
    event.preventDefault();pendingInstall=event;render();
  });
  window.addEventListener("appinstalled",()=>{pendingInstall=null;render();});
  document.addEventListener("DOMContentLoaded",()=>{
    const card=document.querySelector("#exportData")?.closest("article");
    if(!card)return;
    button=document.createElement("button");button.type="button";button.className="secondary";
    button.id="installApp";button.textContent="Установить Student OS";button.hidden=true;
    button.addEventListener("click",async()=>{
      if(!pendingInstall||button.disabled)return;
      const prompt=pendingInstall;pendingInstall=null;button.disabled=true;
      try{await prompt.prompt();await prompt.userChoice;}
      catch{if(typeof toast==="function")toast("Установка недоступна. Попробуйте меню браузера.");}
      finally{button.disabled=false;render();}
    });card.append(button);render();
  });
  if("serviceWorker" in navigator)window.addEventListener("load",async()=>{
    try{
      await navigator.serviceWorker.register("/sw.js",{scope:"/"});
      // Remove only our obsolete registration; never touch another app's workers.
      const registrations=await navigator.serviceWorker.getRegistrations();
      for(const registration of registrations){
        if(registration.scope===location.origin+"/static/"&&
           registration.active?.scriptURL===location.origin+"/static/sw.js")await registration.unregister();
      }
    }catch{/* Online app remains usable when workers are unavailable. */}
  });
})();
