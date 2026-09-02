const state = {
  lessons: [], deadlines: [], preferences: null,
  calendarDate: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
};
const dayNames = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];
const shortDays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

const api = async (url, options = {}) => {
  const response = await fetch(url, {headers: {"Content-Type": "application/json"}, ...options});
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Ошибка ${response.status}`);
  }
  return response.json();
};

const escapeText = value => String(value ?? "");
const localDateKey = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
const parseLocalDate = value => new Date(value.length === 10 ? `${value}T00:00:00` : value);

function toast(message) {
  const node = document.querySelector("#toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2600);
}

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = text;
  return node;
}

function navigate(target) {
  document.querySelectorAll(".page").forEach(page => page.classList.toggle("active", page.id === target));
  document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.target === target));
  const titles = {today: "Сегодня", schedule: "Расписание", study: "AI Study", calendar: "Календарь"};
  document.querySelector("#pageTitle").textContent = titles[target];
  window.location.hash = target;
}

function lessonDetails(lesson) {
  const labels = {room: "Кабинет", teacher: "Преподаватель", lesson_type: "Тип", group_name: "Группа", notes: "Заметки"};
  return state.preferences.visible_fields
    .filter(field => lesson[field])
    .map(field => `${labels[field]}: ${lesson[field]}`);
}

function lessonNode(lesson) {
  const card = element("article", "lesson-card");
  card.append(element("div", "lesson-time", `${lesson.starts_at}–${lesson.ends_at}`));
  card.append(element("h3", "", lesson.subject));
  lessonDetails(lesson).forEach(value => card.append(element("p", "lesson-detail", value)));
  return card;
}

function renderToday() {
  const now = new Date();
  const weekday = (now.getDay() + 6) % 7;
  const today = state.lessons.filter(item => item.weekday === weekday);
  const container = document.querySelector("#todayLessons");
  container.replaceChildren();
  if (!today.length) container.append(element("p", "empty-copy", "Сегодня занятий нет."));
  today.forEach(lesson => {
    const row = element("div", "list-item");
    row.append(element("span", "time-badge", lesson.starts_at));
    const copy = element("div"); copy.append(element("h3", "", lesson.subject));
    copy.append(element("p", "muted", lessonDetails(lesson).join(" · ") || `${lesson.starts_at}–${lesson.ends_at}`));
    row.append(copy); container.append(row);
  });
  const minutes = now.getHours() * 60 + now.getMinutes();
  const future = today.find(item => Number(item.ends_at.slice(0,2))*60 + Number(item.ends_at.slice(3)) > minutes);
  document.querySelector("#nextLessonTitle").textContent = future?.subject || (today.length ? "Занятия на сегодня закончились" : "Свободный день");
  document.querySelector("#nextLessonMeta").textContent = future ? `${future.starts_at}–${future.ends_at} · ${future.room || "кабинет не указан"}` : "Можно заняться ближайшим дедлайном.";

  const upcoming = document.querySelector("#upcomingDeadlines"); upcoming.replaceChildren();
  const active = state.deadlines.filter(item => !item.completed).slice(0, 4);
  if (!active.length) upcoming.append(element("p", "empty-copy", "Нет сохранённых дедлайнов."));
  active.forEach(deadline => {
    const row = element("div", "list-item");
    row.append(element("span", "time-badge", parseLocalDate(deadline.due_at).toLocaleDateString("ru", {day:"2-digit", month:"short"})));
    const copy = element("div"); copy.append(element("h3", "", deadline.title));
    copy.append(element("p", "muted", deadline.subject || "Без предмета")); row.append(copy); upcoming.append(row);
  });
}

function renderSchedule() {
  const grid = document.querySelector("#scheduleGrid"); grid.replaceChildren();
  const todayIndex = (new Date().getDay() + 6) % 7;
  const days = state.preferences.schedule_view === "day" ? [todayIndex] : [0,1,2,3,4];
  days.forEach(day => {
    const column = element("section", "day-column");
    const heading = element("p", "day-heading"); heading.append(element("strong", "", dayNames[day]));
    heading.append(document.createTextNode(day === todayIndex ? "Сегодня" : "")); column.append(heading);
    const lessons = state.lessons.filter(item => item.weekday === day);
    if (!lessons.length) column.append(element("div", "card empty-copy", "Занятий нет"));
    lessons.forEach(item => column.append(lessonNode(item))); grid.append(column);
  });
  document.querySelector("#weekView").classList.toggle("active", state.preferences.schedule_view === "week");
  document.querySelector("#dayView").classList.toggle("active", state.preferences.schedule_view === "day");
  document.querySelectorAll("#fieldOptions input").forEach(box => box.checked = state.preferences.visible_fields.includes(box.value));
}

function studyList(title, items) {
  const section = element("section", "study-section"); section.append(element("h3", "", title));
  const list = element("ol", "numbered"); items.forEach(item => list.append(element("li", "", item))); section.append(list);
  return section;
}

function renderStudyResult(result) {
  const root = document.querySelector("#studyResult"); root.className = "study-result card"; root.replaceChildren();
  const intro = element("section", "study-section"); intro.append(element("p", "eyebrow", result.subject));
  intro.append(element("h2", "", result.assignment_title)); intro.append(element("p", "", result.analysis)); root.append(intro);
  const explanation = element("section", "study-section"); explanation.append(element("h3", "", "Объяснение"));
  explanation.append(element("p", "", result.explanation)); root.append(explanation);
  root.append(studyList("Подход", result.approach), studyList("Как проверить", result.checks));
  const defense = element("section", "study-section defense"); defense.append(element("p", "eyebrow", "Как защитить"));
  defense.append(element("blockquote", "", result.how_to_defend));
  defense.append(studyList("Вопросы преподавателя", result.defense_questions));
  defense.append(studyList("Где можно спалиться", result.pitfalls)); root.append(defense);
  const deadline = element("section", "study-section"); deadline.append(element("h3", "", "Добавить дедлайн"));
  deadline.append(element("p", "muted", "Проверьте предложенные данные. AI ничего не сохраняет автоматически."));
  const form = element("form", "deadline-box"); form.id = "deadlineForm";
  const title = document.createElement("input"); title.value = result.assignment_title; title.maxLength = 160; title.required = true; title.setAttribute("aria-label", "Название дедлайна");
  const subject = document.createElement("input"); subject.value = result.subject; subject.maxLength = 120; subject.setAttribute("aria-label", "Предмет");
  const due = document.createElement("input"); due.type = "datetime-local"; due.required = true; due.setAttribute("aria-label", "Дата дедлайна");
  if (result.suggested_due_at) due.value = result.suggested_due_at.slice(0,16);
  const save = element("button", "primary wide", "Сохранить в календарь"); save.type = "submit";
  form.append(title, subject, due, save); deadline.append(form); root.append(deadline);
  form.addEventListener("submit", event => saveDeadline(event, {title, subject, due, save}));
  if (result.mode === "demo") toast("Локальный demo-режим: добавьте OPENAI_API_KEY для живого AI");
}

async function saveDeadline(event, fields) {
  event.preventDefault(); fields.save.disabled = true;
  try {
    const saved = await api("/api/deadlines", {method:"POST", body: JSON.stringify({
      title: fields.title.value, subject: fields.subject.value, due_at: fields.due.value,
      description: document.querySelector("#assignment").value.slice(0, 4000), source:"ai-study",
    })});
    state.deadlines.push(saved); state.deadlines.sort((a,b) => a.due_at.localeCompare(b.due_at));
    renderToday(); renderCalendar(); toast("Дедлайн сохранён и появился в календаре"); fields.save.textContent = "Сохранено ✓";
  } catch (error) { toast(error.message); fields.save.disabled = false; }
}

function renderCalendar() {
  const grid = document.querySelector("#calendarGrid"); grid.replaceChildren();
  shortDays.forEach(day => grid.append(element("div", "weekday", day)));
  const year = state.calendarDate.getFullYear(), month = state.calendarDate.getMonth();
  document.querySelector("#calendarMonth").textContent = state.calendarDate.toLocaleDateString("ru", {month:"long", year:"numeric"});
  const firstOffset = (new Date(year, month, 1).getDay() + 6) % 7;
  const start = new Date(year, month, 1 - firstOffset);
  const todayKey = localDateKey(new Date());
  for (let i=0; i<42; i++) {
    const current = new Date(start); current.setDate(start.getDate()+i); const key = localDateKey(current);
    const cell = element("div", `calendar-day${current.getMonth()===month ? "" : " other"}${key===todayKey ? " today" : ""}`);
    cell.append(element("span", "day-number", current.getDate()));
    state.deadlines.filter(item => item.due_at.slice(0,10) === key).forEach(item => {
      const event = element("button", `calendar-event${item.completed ? " done" : ""}`, item.title);
      event.title = `${item.title} · ${parseLocalDate(item.due_at).toLocaleString("ru")}`;
      event.addEventListener("click", () => toggleDeadline(item)); cell.append(event);
    });
    grid.append(cell);
  }
}

async function toggleDeadline(item) {
  try {
    const updated = await api(`/api/deadlines/${item.id}`, {method:"PATCH", body:JSON.stringify({completed:!item.completed})});
    Object.assign(item, updated); renderCalendar(); renderToday(); toast(item.completed ? "Дедлайн отмечен выполненным" : "Дедлайн возвращён в работу");
  } catch (error) { toast(error.message); }
}

async function savePreferences(patch) {
  const next = {...state.preferences, ...patch};
  try {
    state.preferences = await api("/api/preferences", {method:"PUT", body:JSON.stringify(next)});
    applyTheme(); renderSchedule(); renderToday();
  } catch (error) { toast(error.message); }
}

function applyTheme() { document.documentElement.dataset.theme = state.preferences.theme; }

async function init() {
  document.querySelector("#dateLabel").textContent = new Date().toLocaleDateString("ru", {weekday:"long", day:"numeric", month:"long"});
  try {
    const data = await api("/api/bootstrap"); Object.assign(state, data); applyTheme();
    document.querySelector("#aiMode").textContent = data.ai_mode === "live" ? "AI: подключён" : "AI: demo-режим";
    renderToday(); renderSchedule(); renderCalendar();
  } catch (error) { toast(`Не удалось загрузить Student OS: ${error.message}`); return; }

  document.querySelectorAll(".nav-item").forEach(button => button.addEventListener("click", () => navigate(button.dataset.target)));
  document.querySelectorAll("[data-jump]").forEach(button => button.addEventListener("click", () => navigate(button.dataset.jump)));
  document.querySelector("#themeToggle").addEventListener("click", () => savePreferences({theme: state.preferences.theme === "light" ? "dark" : "light"}));
  document.querySelector("#weekView").addEventListener("click", () => savePreferences({schedule_view:"week"}));
  document.querySelector("#dayView").addEventListener("click", () => savePreferences({schedule_view:"day"}));
  document.querySelector("#fieldOptions").addEventListener("change", () => savePreferences({visible_fields:[...document.querySelectorAll("#fieldOptions input:checked")].map(x=>x.value)}));
  document.querySelector("#prevMonth").addEventListener("click", () => {state.calendarDate.setMonth(state.calendarDate.getMonth()-1); renderCalendar();});
  document.querySelector("#nextMonth").addEventListener("click", () => {state.calendarDate.setMonth(state.calendarDate.getMonth()+1); renderCalendar();});
  const assignment = document.querySelector("#assignment"); assignment.addEventListener("input", () => document.querySelector("#charCount").textContent = `${assignment.value.length.toLocaleString("ru")} / 12 000`);
  document.querySelector("#studyForm").addEventListener("submit", async event => {
    event.preventDefault(); const button = event.currentTarget.querySelector("button[type=submit]"); button.disabled = true; button.textContent = "Разбираю…";
    try {
      const result = await api("/api/study/analyze", {method:"POST", body:JSON.stringify({assignment:assignment.value, subject:document.querySelector("#studySubject").value, title:document.querySelector("#studyTitle").value})});
      renderStudyResult(result);
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = "Получить разбор"; }
  });
  navigate(location.hash.slice(1) || "today");
}

document.addEventListener("DOMContentLoaded", init);
