// Ledgerline UI. Plain JS, no build step. All numbers shown come from the server's code path.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const state = { answers: {}, runId: null };

const KIND = {
  amount_mismatch: "Amount differs", possible_duplicate: "Possible duplicate", unmatched_bank: "Bank line without ledger entry",
  unmatched_ledger: "Ledger entry without bank line", unreadable_row: "Unreadable row",
};

async function health() {
  try {
    const h = await (await fetch("/healthz")).json();
    const l = h.llm;
    $("llm").textContent = `LLM: ${l.state}${l.model ? " · " + l.model : ""}${l.vultr_inference ? " · Vultr Serverless Inference" : " · " + l.endpoint_host}`;
    $("llm").className = "badge " + (l.state === "configured" ? "ok" : "warn");
  } catch { $("llm").textContent = "LLM: status unknown"; }
}

function readFile(input, target) {
  input.addEventListener("change", async () => { if (input.files[0]) $(target).value = await input.files[0].text(); });
}

async function loadDemo() {
  const d = await (await fetch("/api/demo")).json();
  $("bank").value = d.bank_csv; $("ledger").value = d.ledger_csv; state.answers = {};
}

async function run(fresh = true) {
  if (fresh) state.answers = {};
  $("busy").hidden = false; $("run").disabled = true;
  try {
    const res = await fetch("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bank_csv: $("bank").value, ledger_csv: $("ledger").value, answers: state.answers, parent: fresh ? null : state.runId }) });
    const r = await res.json();
    if (!res.ok) throw new Error(typeof r.detail === "string" ? r.detail : (r.detail || []).map((d) => d.msg).join("; ") || `HTTP ${res.status}`);
    state.runId = r.id; render(r);
  } catch (e) { showError(String(e.message || e)); }
  finally { $("busy").hidden = true; $("run").disabled = false; }
}

function showError(msg) { $("error").hidden = false; $("error").innerHTML = `<h2>Could not reconcile</h2><p>${esc(msg)}</p>`; }

function render(r) {
  ["error", "questions", "totalsCard", "excCard", "fuCard", "matchCard"].forEach((id) => ($(id).hidden = true));
  $("traceCard").hidden = false;
  $("total").textContent = `· ${r.total_ms} ms total · run ${r.id}`;
  $("trace").innerHTML = r.trace.map(stepHtml).join("");
  if (r.status === "error") return showError(r.error);
  if (r.questions?.length) renderQuestions(r.questions);
  if (!r.totals) return;
  $("totalsCard").hidden = false; $("totals").innerHTML = totalsHtml(r.totals);
  $("excCard").hidden = false;
  $("exceptions").innerHTML = r.exceptions.length ? r.exceptions.map(excHtml).join("") : "<p>No exceptions.</p>";
  if (r.followups.length) { $("fuCard").hidden = false; $("followups").innerHTML = r.followups.map(fuHtml).join(""); }
  $("matchCard").hidden = false; $("matchCount").textContent = `(${r.matches.length})`;
  $("matches").innerHTML = matchesHtml(r.matches);
}

function stepHtml(s) {
  const { step, status, ms, ...d } = s;
  const detail = Object.entries(d).filter(([, v]) => v !== null && v !== undefined && !(typeof v === "object" && !Object.keys(v).length))
    .map(([k, v]) => `${esc(k)}: ${esc(typeof v === "object" ? JSON.stringify(v) : v)}`).join(" · ");
  return `<li><span class="pill ${esc(status)}">${esc(status)}</span> <b>${esc(step)}</b> <span class="muted">${ms} ms</span><div class="detail">${detail}</div></li>`;
}

function totalsHtml(t) {
  const keys = ["bank_in", "bank_out", "ledger_in", "ledger_out", "matched_bank", "net_difference"];
  return `<table><tr><th>Currency</th>${keys.map((k) => `<th>${k.replace("_", " ")}</th>`).join("")}</tr>` +
    Object.entries(t).map(([c, v]) => `<tr><td><b>${esc(c)}</b></td>${keys.map((k) => `<td class="num">${esc(v[k])}</td>`).join("")}</tr>`).join("") + "</table>";
}

function source(n) {
  if (n.source === "llm") return `<span class="src ok">LLM wording · numbers verified</span>`;
  if (n.source === "llm-checked") return `<span class="src warn">LLM wording · ${esc(n.note)}</span>`;
  return `<span class="src">Template wording · ${esc(n.note || "")}</span>`;
}

function rowsTable(cards) {
  if (!cards.length) return "";
  return `<table class="rows"><tr><th>side</th><th>row</th><th>date</th><th>amount</th><th>ccy</th><th>name / text</th><th>ref</th></tr>` +
    cards.map((c) => c.raw ? `<tr><td>${esc(c.side)}</td><td>${c.row}</td><td colspan="5">${esc(JSON.stringify(c.raw))}</td></tr>` :
      `<tr><td>${esc(c.side)}</td><td>${c.row}</td><td>${esc(c.date)}</td><td class="num">${esc(c.amount)}</td><td>${esc(c.currency)}</td><td>${esc(c.name || c.desc)}</td><td>${esc(c.ref)}</td></tr>`).join("") + "</table>";
}

function excHtml(e) {
  const n = e.narrative;
  return `<div class="exc ${esc(e.kind)}"><div class="head"><span class="kind">${esc(KIND[e.kind] || e.kind)}</span> <span class="muted">${esc(e.id)}</span> ${source(n)}</div>
    <p>${esc(n.text)}</p><p class="next">Next: ${esc(n.next_step)}</p>
    <details><summary>Evidence card</summary><div class="muted">Rule: ${esc(e.rule)}</div>
      <pre>${esc(JSON.stringify(e.facts, null, 1))}</pre>${rowsTable([...e.bank, ...e.ledger])}
      ${n.removed?.length ? `<div class="removed">Removed LLM sentences (number not in evidence):<ul>${n.removed.map((s) => `<li>${esc(s)}</li>`).join("")}</ul></div>` : ""}
    </details></div>`;
}

function fuHtml(f) {
  const d = f.draft;
  return `<div class="fu" id="fu-${esc(f.id)}"><div class="head"><b>${esc(f.counterparty)}</b> · ${esc(f.amount)} ${esc(f.currency)} · ${f.days_overdue} days overdue
    <span class="muted">(due ${esc(f.due)} from ${esc(f.due_source)}, as of ${esc(f.as_of)})</span> ${source(d)}</div>
    <div class="mail"><div><b>Subject:</b> ${esc(d.subject)}</div><pre>${esc(d.body)}</pre></div>
    <button onclick="approve('${esc(f.id)}')" ${f.status !== "draft" ? "disabled" : ""}>${f.status === "draft" ? "Approve draft" : esc(f.status)}</button></div>`;
}

async function approve(fid) {
  const r = await (await fetch(`/api/runs/${state.runId}/followups/${fid}/approve`, { method: "POST" })).json();
  const btn = document.querySelector(`#fu-${fid} button`); btn.disabled = true; btn.textContent = r.followup.status;
}

function matchesHtml(ms) {
  return `<table><tr><th>rule</th><th>bank rows</th><th>ledger rows</th><th>amount</th><th>evidence</th></tr>` + ms.map((m) =>
    `<tr><td>${esc(m.rule)}</td><td>${m.bank.map((b) => b.row).join(", ")}</td><td>${m.ledger.map((l) => l.row).join(", ")}</td>
     <td class="num">${esc(m.ledger.length === 1 ? m.ledger[0].amount : m.bank[0].amount)} ${esc(m.bank[0].currency)}</td><td class="muted">${esc(JSON.stringify(m.evidence))}</td></tr>`).join("") + "</table>";
}

function renderQuestions(qs) {
  $("questions").hidden = false;
  $("questions").innerHTML = "<h2>The agent needs you</h2><p class='muted'>It stopped instead of guessing.</p>" + qs.map(questionHtml).join("") +
    `<button onclick="answer()">Answer and re-run</button>`;
}

function questionHtml(q, i) {
  if (q.type === "column_mapping") {
    const opts = (sel) => q.headers.map((h) => `<option ${h === sel ? "selected" : ""}>${esc(h)}</option>`).join("");
    const roles = q.missing;
    return `<div class="q" data-i="${i}" data-type="column_mapping" data-side="${esc(q.side)}"><p>${esc(q.text)}</p>
      ${q.suggested && Object.keys(q.suggested).length ? `<p class="muted">LLM suggestion (pre-filled, please confirm): ${esc(q.suggestion_reason || "")}</p>` : ""}
      ${roles.map((r) => `<label>${r} <select data-role="${r}">${opts((q.suggested || {})[r])}</select></label>`).join(" ")}
      <pre>${esc(JSON.stringify(q.sample, null, 1))}</pre></div>`;
  }
  if (q.type === "date_format")
    return `<div class="q" data-type="date_format" data-side="${esc(q.side)}"><p>${esc(q.text)}</p><p class="muted">Examples: ${esc(q.examples.join(", "))}</p>
      <label><input type="radio" name="df-${esc(q.side)}" value="dmy" checked> day first</label> <label><input type="radio" name="df-${esc(q.side)}" value="mdy"> month first</label></div>`;
  if (q.type === "ambiguous_match") {
    // Each option is a whole grouping {bank:[...], ledger:[...]}; the server re-checks that the amounts agree.
    const opts = q.combos
      ? q.combos.map((c) => q.split_side === "b" ? { bank: c, ledger: q.ledger } : { bank: q.bank, ledger: c })
      : q.ledger.length > 1 ? q.ledger.map((l) => ({ bank: [q.bank[0]], ledger: [l] }))
      : q.bank.map((b) => ({ bank: [b], ledger: [q.ledger[0]] }));
    const radios = opts.map((o) => `<label><input type="radio" name="amb-${i}" value='${esc(JSON.stringify(o))}'> bank row ${o.bank.join(" + ")} ↔ ledger row ${o.ledger.join(" + ")}</label>`);
    return `<div class="q" data-type="ambiguous_match" data-i="${i}"><p>${esc(q.amount)} ${esc(q.currency)}: ${esc(q.text)}</p>${radios.join("<br>")}
      <br><label><input type="radio" name="amb-${i}" value="" checked> leave open</label></div>`;
  }
  return `<div class="q"><p>${esc(q.text || q.type)}</p></div>`;
}

function answer() {
  document.querySelectorAll("#questions .q").forEach((el) => {
    const side = el.dataset.side;
    if (el.dataset.type === "column_mapping") {
      state.answers.mapping = state.answers.mapping || {};
      state.answers.mapping[side] = Object.fromEntries([...el.querySelectorAll("select")].map((s) => [s.dataset.role, s.value]));
    } else if (el.dataset.type === "date_format") {
      state.answers.date_format = { ...(state.answers.date_format || {}), [side]: el.querySelector("input:checked").value };
    } else if (el.dataset.type === "ambiguous_match") {
      const v = el.querySelector("input:checked")?.value;
      if (v) (state.answers.pairs = state.answers.pairs || []).push(JSON.parse(v));
    }
  });
  run(false);
}

readFile($("bankFile"), "bank"); readFile($("ledgerFile"), "ledger");
$("demo").onclick = loadDemo; $("run").onclick = () => run(true);
health();
