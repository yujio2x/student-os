// Account actions are also bound before bootstrap, so production login needs no dev session.
function canonicalAuthState(){const mode=state.session?.mode,linked=Boolean(state.telegram?.identity);if(!state.session)return"loading";if(mode==="guest"&&!linked)return"guest";if(mode==="telegram"&&linked)return state.session.user?.role==="admin"?"owner":"telegram";return"unknown";}
async function beginTelegramLogin(button){
  button.disabled=true;const original=button.textContent;button.textContent="Открываю Telegram…";
  try{sessionStorage.setItem("student-os-auth-return",location.hash||"#today");const result=await api("/api/auth/telegram/start",{method:"POST"});location.assign(result.url);}
  catch(error){toast(error.message);document.querySelector("#loginError").textContent=error.message;}
  finally{button.disabled=false;button.textContent=original;}
}
async function showLogin(){
  const options=await api("/api/auth/options").catch(()=>({}));
  document.querySelector("#loginTelegram").disabled=!options.telegram_login;
  document.querySelector("#loginError").textContent=options.telegram_login?"Войдите в свой Telegram-аккаунт. Баланс и данные будут доступны на этом устройстве.":"Вход пока не настроен владельцем сервиса. Ваши данные не изменены.";
  const dialog=document.querySelector("#loginDialog");if(!dialog.open)dialog.showModal();
}
function renderAccountActions(){
  if(typeof renderPhotoAccess==="function")renderPhotoAccess();
  const auth=canonicalAuthState(),linked=auth==="telegram"||auth==="owner",guest=auth==="guest",entitlement=state.student_ai_entitlement;
  const connect=document.querySelector("#connectTelegram"),buy=document.querySelector("#accountBuy");
  connect.hidden=!guest;connect.disabled=!state.telegram?.login_available;connect.textContent="Войти через Telegram";
  document.querySelector("#accountRefresh").hidden=!linked;
  document.querySelector("#accountLogout").hidden=!linked;
  buy.hidden=!(linked&&entitlement?.purchase_url);
  if(!buy.hidden)buy.href=entitlement.purchase_url;
}
let logoutPending=false;
async function accountRequest(url,options={}){const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),globalThis.STUDENT_OS_ACCOUNT_TIMEOUT_MS||10000);try{return await api(url,{...options,signal:controller.signal});}catch(error){if(controller.signal.aborted)throw new Error("Запрос занял слишком много времени. Повторите.");throw error;}finally{clearTimeout(timeout);}}
async function confirmAccountLogout(button){
  if(logoutPending)return;
  logoutPending=true;const original=button.textContent,dialog=document.querySelector("#logoutDialog"),errorNode=document.querySelector("#logoutError");
  button.disabled=true;button.textContent="Выходим…";errorNode.textContent="";
  try{await accountRequest("/api/auth/logout",{method:"POST"});}
  catch(error){errorNode.textContent=error.message;toast(error.message);button.disabled=false;button.textContent=original;logoutPending=false;return;}
  if(dialog.open)dialog.close();
  clearPrivateClientState();
  try{
    await accountRequest("/api/auth/guest",{method:"POST"});
    const bootstrap=await accountRequest("/api/bootstrap");
    if(bootstrap.session?.mode!=="guest"||bootstrap.telegram?.identity)throw new Error("Некорректное гостевое состояние");
    applyBootstrapState(bootstrap);navigate("today");toast("Вы вышли. Доступен гостевой режим.");
  }catch(error){toast("Сеанс завершён. Перезагружаю гостевой режим…");location.replace("/#today");}
  finally{button.disabled=false;button.textContent=original;logoutPending=false;}
}
document.addEventListener("DOMContentLoaded",()=>{
  for(const id of ["connectTelegram","loginTelegram"])document.querySelector(`#${id}`).addEventListener("click",event=>beginTelegramLogin(event.currentTarget));
  document.querySelector("#accountRefresh").addEventListener("click",()=>refreshEntitlement(true));
  document.querySelector("#accountLogout").addEventListener("click",()=>{if(["telegram","owner"].includes(canonicalAuthState())){document.querySelector("#logoutError").textContent="";document.querySelector("#logoutDialog").showModal();}});
  document.querySelector("#cancelLogout").addEventListener("click",()=>{if(!logoutPending)document.querySelector("#logoutDialog").close();});
  document.querySelector("#confirmLogout").addEventListener("click",event=>confirmAccountLogout(event.currentTarget));
  const params=new URLSearchParams(location.search),result=params.get("telegram");
  if(result){
    const messages={connected:"Telegram подключён",conflict:"Этот Telegram уже связан с другим аккаунтом. Выйдите и войдите через Telegram; текущие данные сохранятся в прежнем аккаунте.",expired:"Время входа истекло. Нажмите «Подключить Telegram» ещё раз.",cancelled:"Вход отменён. Можно повторить позже.",failed:"Не удалось подтвердить вход. Повторите попытку."};
    document.querySelector("#accountNotice").textContent=messages[result]||"";
    const returnTo=result==="connected"?sessionStorage.getItem("student-os-auth-return"):"";
    sessionStorage.removeItem("student-os-auth-return");
    history.replaceState(null,"",location.pathname+(returnTo||location.hash));
  }
});
