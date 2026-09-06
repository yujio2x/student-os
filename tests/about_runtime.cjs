const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

function node(){return{hidden:true,textContent:"",href:undefined,removeAttribute(name){if(name==="href")this.href=undefined;}};}
const ids=["aboutName","aboutVersion","aboutDescription","aboutGithub","aboutGithubLabel","aboutTelegram","aboutTelegramLabel","aboutSupport","aboutSupportLabel"];
const elements=Object.fromEntries(ids.map(id=>[id,node()]));
const document={querySelector:selector=>elements[selector.slice(1)]};
const context={URL};context.globalThis=context;
vm.runInNewContext(fs.readFileSync("static/about.js","utf8"),context);

const base={name:"Student OS",version:"v0.1 Beta",description:"Student OS — приложение для студентов с расписанием, дедлайнами, календарём и Student AI.",github_url:"https://github.com/yujio2x/student-os",telegram_url:"",support_email:""};
context.StudentOSAbout.render(base,document);
assert.equal(elements.aboutName.textContent,"Student OS");assert.equal(elements.aboutVersion.textContent,"v0.1 Beta");
assert.equal(elements.aboutGithub.href,"https://github.com/yujio2x/student-os");assert.equal(elements.aboutGithub.hidden,false);
assert.equal(elements.aboutTelegram.hidden,true);assert.equal(elements.aboutTelegram.href,undefined);
assert.equal(elements.aboutSupport.hidden,true);assert.equal(elements.aboutSupport.href,undefined);

context.StudentOSAbout.render({...base,telegram_url:"https://t.me/student_os",support_email:"support@example.kz"},document);
assert.equal(elements.aboutTelegram.href,"https://t.me/student_os");assert.equal(elements.aboutTelegram.hidden,false);
assert.equal(elements.aboutSupport.href,"mailto:support@example.kz");assert.equal(elements.aboutSupport.hidden,false);
context.StudentOSAbout.render({...base,telegram_url:"javascript:alert(1)",support_email:"invalid"},document);
assert.equal(elements.aboutTelegram.hidden,true);assert.equal(elements.aboutTelegram.href,undefined);
assert.equal(elements.aboutSupport.hidden,true);assert.equal(elements.aboutSupport.href,undefined);
context.StudentOSAbout.render({...base,github_url:"https://example.com/project",telegram_url:"https://example.com/channel"},document);
assert.equal(elements.aboutGithub.hidden,true);assert.equal(elements.aboutTelegram.hidden,true);

const html=fs.readFileSync("static/index.html","utf8");
assert.match(html,/id="aboutSettings"/);assert.match(html,/id="aboutGithub" target="_blank" rel="noopener noreferrer"/);
assert.match(html,/id="aboutTelegram" target="_blank" rel="noopener noreferrer"/);assert.doesNotMatch(html,/href=""/);
console.log("About runtime: required details, optional contacts and safe links passed");
