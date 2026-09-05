(function initializeStudentAIUX(root){
  function gate(auth,entitlement,reason=""){
    if(reason==="login-required")return{
      title:"Войдите через Telegram ещё раз",
      detail:"Сессия входа завершилась. После повторного входа можно продолжить разбор.",
      primary:"Войти через Telegram",secondary:"Отмена",action:"login",href:"#",
    };
    if(auth!=="telegram"&&auth!=="owner")return{
      title:"Войдите через Telegram, чтобы использовать Student AI",
      detail:"Вход откроет Student AI и синхронизацию между устройствами. Расписание, календарь и дедлайны продолжат работать без него.",
      primary:"Войти через Telegram",secondary:"Отмена",action:"login",href:"#",
    };
    if(!entitlement?.connected)return{
      title:"Student AI временно недоступен",
      detail:"Не удалось проверить доступ. Откройте настройки и обновите баланс.",
      primary:"Открыть настройки",secondary:"Отмена",action:"settings",href:"#",
    };
    if(entitlement.purchase_url)return{
      title:"Закончились попытки Student AI",
      detail:"Для нового разбора нужна ещё одна попытка.",
      primary:"Купить попытки",secondary:"Отмена",action:"purchase",href:entitlement.purchase_url,
    };
    return{
      title:"Закончились попытки Student AI",
      detail:"Для нового разбора нужна ещё одна попытка. Покупка сейчас недоступна — попробуйте позже.",
      primary:null,secondary:"Закрыть",action:"close",href:"#",
    };
  }
  root.StudentAIUX=Object.freeze({gate});
})(globalThis);
