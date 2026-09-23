const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let JOBS = [];

// ---------------- results table ----------------
async function load() {
  try {
    const r = await fetch("data/jobs.json", { cache: "no-store" });
    const data = await r.json();
    JOBS = data.jobs || [];
    $("#stat-count").textContent = JOBS.length;
    $("#stat-open").textContent = JOBS.filter(j => j.still_open).length;
    $("#stat-updated").textContent = data.updated ? ago(data.updated) : "not yet";
  } catch {
    JOBS = [];
    $("#stat-count").textContent = "0";
    $("#stat-open").textContent = "0";
    $("#stat-updated").textContent = "not yet";
  }
  render();
}

function ago(iso) {
  const d = Math.round((Date.now() - new Date(iso)) / 86400000);
  return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d} days ago`;
}

function render() {
  const q = $("#q").value.toLowerCase().trim();
  const openOnly = $("#open-only").checked;
  const rows = JOBS.filter(j => (!openOnly || j.still_open) &&
    (!q || `${j.title} ${j.company} ${j.location}`.toLowerCase().includes(q)));
  const empty = $("#empty");
  if (!JOBS.length) {
    empty.textContent = "No matches yet. The first scheduled run will fill this in.";
  } else if (!rows.length) {
    empty.textContent = "Nothing matches that filter.";
  }
  empty.hidden = rows.length > 0;
  document.querySelector(".table-wrap").hidden = rows.length === 0;
  $("#rows").innerHTML = rows.map((j, i) => `
    <tr class="job${j.still_open ? "" : " closed"}" data-i="${i}" tabindex="0" aria-expanded="false">
      <td><span class="score s${j.score}">${j.score}</span></td>
      <td class="role"><b>${esc(j.title)}</b><span>${esc(j.company)}${j.duration ? " · " + esc(j.duration) : ""}</span></td>
      <td>${esc(j.location)}</td>
      <td class="pay${j.salary ? "" : " none"}">${j.salary ? esc(j.salary) : "Not stated"}</td>
      <td>${j.still_open ? `<span class="chip ${j.freshness}">${j.freshness}</span>` : `<span class="chip closed">closed</span>`}
          <span class="days">${j.days_live ?? "?"}d live</span></td>
      <td><a class="apply" href="${esc(j.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Apply ↗</a></td>
    </tr>`).join("");
  $("#rows").querySelectorAll("tr.job").forEach(tr => {
    const toggle = () => expand(tr, rows[+tr.dataset.i]);
    tr.addEventListener("click", toggle);
    tr.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
  });
}

function expand(tr, j) {
  const next = tr.nextElementSibling;
  if (next?.classList.contains("detail")) { next.remove(); tr.setAttribute("aria-expanded", "false"); return; }
  tr.setAttribute("aria-expanded", "true");
  tr.insertAdjacentHTML("afterend", `<tr class="detail"><td></td><td colspan="5">
    <p>${esc(j.why_it_fits)}</p>
    ${(j.tailored_bullets || []).length ? `<ul>${j.tailored_bullets.map(b => `<li>${esc(b)}</li>`).join("")}</ul>` : ""}
    <p class="meta">${j.open_roles_at_company} roles open at ${esc(j.company)} · found ${esc(j.found_on)}</p>
  </td></tr>`);
}

$("#q").addEventListener("input", render);
$("#open-only").addEventListener("change", render);

// ---------------- chat ----------------
const history = [];
function say(text, cls) {
  const el = document.createElement("div");
  el.className = `msg ${cls}`;
  el.innerHTML = esc(text).replace(/(https?:\/\/[^\s)]+)/g, '<a href="$1" target="_blank" rel="noopener">link ↗</a>');
  $("#log").appendChild(el);
  $("#log").scrollTop = $("#log").scrollHeight;
  return el;
}

async function ask(text) {
  text = text.trim();
  if (!text) return;
  $("#chips")?.remove();
  say(text, "user");
  history.push({ role: "user", text });
  const wait = say("Looking through the matches…", "bot thinking");
  const btn = $("#chat-form button");
  btn.disabled = true;
  try {
    const r = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ messages: history.slice(-12) }) });
    const data = await r.json();
    wait.remove();
    if (!r.ok) { say(data.error || "Something went wrong.", "bot err"); history.pop(); return; }
    say(data.reply, "bot");
    history.push({ role: "assistant", text: data.reply });
  } catch {
    wait.remove();
    say("Couldn't reach the server. Check your connection and try again.", "bot err");
    history.pop();
  } finally {
    btn.disabled = false;
  }
}
$("#chat-form").addEventListener("submit", e => { e.preventDefault(); const v = $("#chat-in").value; $("#chat-in").value = ""; ask(v); });
$("#chips").addEventListener("click", e => { if (e.target.tagName === "BUTTON") ask(e.target.textContent); });

// ---------------- resume match ----------------
if (window.pdfjsLib) pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

async function pdfText(file) {
  const pdf = await pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
  let out = "";
  for (let p = 1; p <= Math.min(pdf.numPages, 5); p++) {
    const page = await pdf.getPage(p);
    out += (await page.getTextContent()).items.map(i => i.str).join(" ") + "\n";
  }
  return out;
}

$("#resume").addEventListener("change", async e => {
  const file = e.target.files[0];
  const out = $("#match-out");
  if (!file) return;
  $("#resume-label").textContent = file.name;
  out.innerHTML = `<p class="muted">Reading the PDF and scoring the open matches. This takes about 20 seconds.</p>`;
  try {
    const resume = await pdfText(file);
    const r = await fetch("/api/match", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ resume }) });
    const data = await r.json();
    if (!r.ok) { out.innerHTML = `<p class="msg err">${esc(data.error)}</p>`; return; }
    out.innerHTML = `<p class="muted">Scored ${data.scored_against} open roles against your resume (using each job's summary):</p>
      <ol>${data.results.slice(0, 8).map(x => `<li><b>${x.score}/10</b> <a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a> · ${esc(x.company)}<small>${esc(x.reason)}</small></li>`).join("")}</ol>`;
  } catch {
    out.innerHTML = `<p class="msg err">Couldn't read that file. Make sure it's a text-based PDF, not a scan.</p>`;
  }
});

load();
