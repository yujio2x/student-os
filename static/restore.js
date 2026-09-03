let restorePreview=null;
document.addEventListener("DOMContentLoaded",()=>{
  const action=document.createElement("button");action.type="button";action.className="setting-action";action.id="restoreData";
  action.innerHTML='<span><strong>Восстановить из JSON</strong><small>Предпросмотр и подтверждение замены моих данных</small></span><span>↑</span>';
  const placeholder=[...document.querySelectorAll("#dataSettings .setting-action.disabled")].find(item=>item.querySelector("strong")?.textContent==="Восстановление и очистка");
  if(placeholder)placeholder.replaceWith(action);else document.querySelector("#dataSettings").append(action);
  const dialog=document.createElement("dialog");dialog.className="modal";dialog.id="restoreDialog";
  dialog.innerHTML='<div class="modal-card"><h2>Восстановить мои данные</h2><p class="muted">Архив заменит ваши занятия, дедлайны и настройки. Баланс, Telegram и данные других пользователей не изменятся. Сначала сохраните текущий экспорт.</p><label>JSON-архив до 5 МБ<input id="restoreFile" type="file" accept="application/json,.json"></label><button id="previewRestore" class="secondary" type="button">Проверить архив</button><p id="restoreError" class="form-error" role="alert"></p><div id="restoreSummary" hidden><p id="restoreCounts"></p><label class="photo-task"><input id="restoreConsent" type="checkbox"><span>Подтверждаю замену моих текущих занятий, дедлайнов и настроек</span></label><button id="confirmRestore" class="primary" type="button" disabled>Заменить мои данные</button></div><div class="account-actions"><button id="closeRestore" class="secondary" type="button">Отмена</button></div></div>';
  document.body.append(dialog);
  action.addEventListener("click",()=>{restorePreview=null;document.querySelector("#restoreSummary").hidden=true;document.querySelector("#restoreError").textContent="";dialog.showModal();});
  document.querySelector("#closeRestore").addEventListener("click",()=>dialog.close());
  document.querySelector("#restoreFile").addEventListener("change",()=>{restorePreview=null;document.querySelector("#restoreSummary").hidden=true;});
  function upload(){const file=document.querySelector("#restoreFile").files[0];if(!file||file.size>5*1024*1024)throw new Error("Выберите JSON-архив до 5 МБ");const form=new FormData();form.append("file",file);return form;}
  async function run(button,operation){button.disabled=true;document.querySelector("#restoreError").textContent="";try{await operation();}catch(error){document.querySelector("#restoreError").textContent=error.message;}finally{button.disabled=false;}}
  document.querySelector("#previewRestore").addEventListener("click",event=>run(event.currentTarget,async()=>{
    restorePreview=await api("/api/restore/preview",{method:"POST",body:upload()});
    const before=restorePreview.current,after=restorePreview.replacement;
    document.querySelector("#restoreCounts").textContent=`Занятия: ${before.lessons} → ${after.lessons}. Дедлайны: ${before.deadlines} → ${after.deadlines}. Настройки будут заменены. Ничего не сохранено; подтверждение действительно 5 минут.`;
    document.querySelector("#restoreConsent").checked=false;document.querySelector("#confirmRestore").disabled=true;document.querySelector("#restoreSummary").hidden=false;
  }));
  document.querySelector("#restoreConsent").addEventListener("change",event=>document.querySelector("#confirmRestore").disabled=!event.target.checked);
  document.querySelector("#confirmRestore").addEventListener("click",event=>run(event.currentTarget,async()=>{
    if(!restorePreview||!document.querySelector("#restoreConsent").checked)throw new Error("Проверьте архив и подтвердите замену");
    const form=upload();form.append("preview_id",restorePreview.preview_id);form.append("confirm_replace","true");
    await api("/api/restore/confirm",{method:"POST",body:form});restorePreview=null;location.reload();
  }));
});
