// Account actions are also bound before bootstrap, so production login needs no dev session.
async function beginTelegramLogin(button){
  button.disabled=true;const original=button.textContent;button.textContent="Открываю Telegram…";
  try{const result=await api("/api/auth/telegram/start",{method:"POST"});location.assign(result.url);}
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
  const linked=Boolean(state.telegram?.identity),entitlement=state.student_ai_entitlement;
  const connect=document.querySelector("#connectTelegram"),buy=document.querySelector("#accountBuy");
  connect.hidden=linked;connect.disabled=!state.telegram?.login_available;
  document.querySelector("#accountRefresh").hidden=!linked;
  document.querySelector("#accountLogout").hidden=!state.session;
  buy.hidden=!(linked&&entitlement?.purchase_url);
  if(!buy.hidden)buy.href=entitlement.purchase_url;
}
document.addEventListener("DOMContentLoaded",()=>{
  for(const id of ["connectTelegram","loginTelegram"])document.querySelector(`#${id}`).addEventListener("click",event=>beginTelegramLogin(event.currentTarget));
  document.querySelector("#accountRefresh").addEventListener("click",()=>refreshEntitlement(true));
  document.querySelector("#accountLogout").addEventListener("click",()=>document.querySelector("#logoutDialog").showModal());
  document.querySelector("#cancelLogout").addEventListener("click",()=>document.querySelector("#logoutDialog").close());
  document.querySelector("#confirmLogout").addEventListener("click",async event=>{
    event.currentTarget.disabled=true;
    try{await api("/api/auth/logout",{method:"POST"});location.replace("/?logged_out=1");}
    catch(error){toast(error.message);event.currentTarget.disabled=false;}
  });
  const params=new URLSearchParams(location.search),result=params.get("telegram");
  if(result){
    const messages={connected:"Telegram подключён",conflict:"Этот Telegram уже связан с другим аккаунтом. Выйдите и войдите через Telegram; текущие данные сохранятся в прежнем аккаунте.",expired:"Время входа истекло. Нажмите «Подключить Telegram» ещё раз.",cancelled:"Вход отменён. Можно повторить позже.",failed:"Не удалось подтвердить вход. Повторите попытку."};
    document.querySelector("#accountNotice").textContent=messages[result]||"";
    history.replaceState(null,"",location.pathname+location.hash);
  }
});
