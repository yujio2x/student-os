const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

const context={};context.globalThis=context;
vm.runInNewContext(fs.readFileSync("static/student-ai-ux.js","utf8"),context);

const purchase=context.StudentAIUX.gate("owner",{connected:true,purchase_url:"https://t.me/example?start=buy"});
assert.deepEqual(JSON.parse(JSON.stringify(purchase)),{title:"Закончились попытки Student AI",detail:"Для нового разбора нужна ещё одна попытка.",primary:"Купить попытки",secondary:"Отмена",action:"purchase",href:"https://t.me/example?start=buy"});
const unavailable=context.StudentAIUX.gate("telegram",{connected:true,purchase_url:""});
assert.equal(unavailable.primary,null);assert.equal(unavailable.secondary,"Закрыть");assert.match(unavailable.detail,/Покупка сейчас недоступна/);
const guest=context.StudentAIUX.gate("guest",null);assert.equal(guest.action,"login");assert.equal(guest.primary,"Войти через Telegram");
const disconnected=context.StudentAIUX.gate("telegram",{connected:false});assert.equal(disconnected.action,"settings");assert.equal(disconnected.primary,"Открыть настройки");
const expired=context.StudentAIUX.gate("owner",{connected:true,purchase_url:"https://t.me/example"},"login-required");assert.equal(expired.action,"login");assert.equal(expired.primary,"Войти через Telegram");

for(const model of [purchase,unavailable,guest,disconnected,expired])assert.doesNotMatch(JSON.stringify(model),/credits|entitlement|insufficient balance|\btrial\b|\bunlimited\b/i);
const publicCopy=[fs.readFileSync("static/index.html","utf8"),fs.readFileSync("static/app.js","utf8")].join("\n");
assert.doesNotMatch(publicCopy,/Недостаточно credits|Unified ledger|\b\d+ credits\b|Нужны попытки Student AI/);
console.log("Student AI UX: purchase, unavailable, guest and disconnected copy/actions passed");
