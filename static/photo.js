let photoQuote=null,photoSession=null,photoRestored=false;
function showPhotoSession(session){photoSession=session;document.querySelector("#photoCount").textContent=`Найдено задач: ${session.tasks.length}`;const list=document.querySelector("#photoTasks");list.replaceChildren();session.tasks.forEach((text,index)=>{const label=document.createElement("label"),input=document.createElement("input"),span=document.createElement("span");label.className="photo-task";input.type="checkbox";input.value=String(index);input.checked=true;span.textContent=text;label.append(input,span);list.append(label);});document.querySelector("#photoSelection").hidden=false;}
function renderPhotoAccess(){const button=document.querySelector("#photoQuoteButton");if(button)button.disabled=!state.photo_available;if(state.photo_available&&state.telegram?.identity&&!photoRestored){photoRestored=true;api("/api/study/photo/session").then(data=>{if(data.session)showPhotoSession(data.session);}).catch(()=>{});}}
function photoUpload(){const file=document.querySelector("#studyPhoto").files[0];if(!file)throw new Error("Выберите PNG или JPEG");if(file.size>6*1024*1024)throw new Error("Фото должно быть не больше 6 МБ");const data=new FormData();data.append("file",file);return data;}
async function photoAction(button,operation){button.disabled=true;document.querySelector("#photoError").textContent="";try{await operation();}catch(error){document.querySelector("#photoError").textContent=error.message;}finally{button.disabled=false;}}
document.addEventListener("DOMContentLoaded",()=>{
  const box=document.createElement("section");box.className="photo-input";
  box.innerHTML='<h3>Разобрать фото</h3><p class="muted">PNG или JPEG до 6 МБ. Сначала покажем стоимость. Условия сохраняются на 24 часа; само фото не сохраняется.</p><label>Фотография задания<input id="studyPhoto" type="file" accept="image/png,image/jpeg"></label><button id="photoQuoteButton" class="secondary" type="button" disabled>Узнать стоимость</button><p id="photoError" class="form-error" role="alert"></p><div id="photoQuote" hidden><p id="photoCost"></p><button id="photoConfirm" class="primary" type="button">Подтвердить и распознать</button></div><div id="photoSelection" hidden><h3 id="photoCount"></h3><div id="photoTasks"></div><div class="account-actions"><button id="photoAll" type="button" class="secondary">Выбрать все</button><button id="photoAnswer" type="button" class="primary">Разобрать выбранные</button></div><p class="muted">Другие задачи с этого фото — без повторного списания. До 20 запросов в час.</p></div>';
  document.querySelector(".future-input").replaceWith(box);
  document.querySelector("#studyPhoto").addEventListener("change",()=>{photoQuote=null;document.querySelector("#photoQuote").hidden=true;});
  document.querySelector("#photoQuoteButton").addEventListener("click",event=>photoAction(event.currentTarget,async()=>{
    if(!state.telegram?.identity){showStudentAIGate();return;}
    photoQuote=await api("/api/study/photo/quote",{method:"POST",body:photoUpload()});
    document.querySelector("#photoCost").textContent=photoQuote.uses_trial?"Будет использована одна общая бесплатная попытка.":photoQuote.credits?"Распознавание и фото-сессия: 5 оплаченных попыток (пакет — 100 Stars).":"Безлимит: попытки не списываются.";
    document.querySelector("#photoConfirm").disabled=!photoQuote.can_confirm;document.querySelector("#photoQuote").hidden=false;
    if(!photoQuote.can_confirm)document.querySelector("#photoError").textContent="Недостаточно попыток. Купите пакет в Telegram и обновите баланс.";
  }));
  document.querySelector("#photoConfirm").addEventListener("click",event=>photoAction(event.currentTarget,async()=>{
    if(!photoQuote)throw new Error("Получите новую стоимость");
    const data=photoUpload();data.append("quote_id",photoQuote.quote_id);photoQuote=null;
    document.querySelector("#photoQuote").hidden=true;
    photoSession=await api("/api/study/photo/confirm",{method:"POST",body:data});
    document.querySelector("#studyPhoto").value="";
    showPhotoSession(photoSession);await refreshEntitlement();
  }));
  document.querySelector("#photoAll").addEventListener("click",()=>document.querySelectorAll("#photoTasks input").forEach(x=>x.checked=true));
  document.querySelector("#photoAnswer").addEventListener("click",event=>photoAction(event.currentTarget,async()=>{
    const selection=[...document.querySelectorAll("#photoTasks input:checked")].map(x=>Number(x.value));
    if(!selection.length)throw new Error("Выберите хотя бы одну задачу");
    renderStudyResult(await api("/api/study/photo/answer",{method:"POST",body:JSON.stringify({session_id:photoSession.session_id,selection,request_id:crypto.randomUUID()})}));
  }));
});
