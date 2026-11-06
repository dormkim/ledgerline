// Ledgerline UI. Plain JS, no build step, no inline handlers (the server sends a strict CSP).
// Every number shown comes from the server's code path; the browser only formats and lays out.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const state = { answers: {}, runId: null };

const KIND = {
  amount_mismatch: "Amount differs", possible_duplicate: "Possible duplicate", unmatched_bank: "Bank line without ledger entry",
  unmatched_ledger: "Ledger entry without bank line", unreadable_row: "Unreadable row",
};
const KIND_SHORT = {
  amount_mismatch: "amount differs", possible_duplicate: "possible duplicate", unmatched_bank: "bank only",
  unmatched_ledger: "ledger only", unreadable_row: "unreadable",
};
const TOTAL_LABEL = { bank_in: "Bank in", bank_out: "Bank out", ledger_in: "Ledger in", ledger_out: "Ledger out",
  matched_bank: "Matched (bank, net)", net_difference: "Net difference (bank minus ledger)" };

async function health() {
  try {
    const h = await (await fetch("/healthz")).json();
    const l = h.llm;
    // Name the inference service only when it is really in use; otherwise say the wording comes from templates.
    $("llm").textContent = l.state === "configured"
      ? `LLM: ${l.model} · ${l.vultr_inference ? "Vultr Serverless Inference" : l.endpoint_host}`
      : `LLM ${l.state === "disabled" ? "off" : "not configured"} · template wording, same numbers`;
    $("llm").className = "badge " + (l.state === "configured" ? "ok" : "warn");
  } catch { $("llm").textContent = "LLM: status unknown"; }
}

async function loadSamples() {
  try {
    const sets = await (await fetch("/api/samples")).json();
    $("sampleSet").innerHTML = sets.map((s) => `<option value="${esc(s.id)}">${esc(s.label)}</option>`).join("");
    const want = new URLSearchParams(location.search).get("set");
    if (want && sets.some((s) => s.id === want)) $("sampleSet").value = want;
  } catch { /* keep the default option */ }
}

function readFile(input, target) {
  input.addEventListener("change", async () => { if (input.files[0]) $(target).value = await input.files[0].text(); });
}

async function loadDemo() {
  const d = await (await fetch(`/api/demo?set=${encodeURIComponent($("sampleSet").value)}`)).json();
  $("bank").value = d.bank_csv; $("ledger").value = d.ledger_csv; state.answers = {};
}

async function tryDemo() {
  $("tryDemo").disabled = true;
  try { await loadDemo(); await run(true); } finally { $("tryDemo").disabled = false; }
}

async function run(fresh = true) {
  if (fresh) state.answers = {};
  if (!$("bank").value.trim() || !$("ledger").value.trim()) {
    $("uploadBox").open = true;
    return showError("Add both files first: a bank statement and a ledger (or run the sample).");
  }
  $("busy").hidden = false; $("run").disabled = true;
  try {
    const res = await fetch("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bank_csv: $("bank").value, ledger_csv: $("ledger").value, answers: state.answers, parent: fresh ? null : state.runId }) });
    const r = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    if (!res.ok) throw new Error(typeof r.detail === "string" ? r.detail : (r.detail || []).map((d) => d.msg).join("; ") || `HTTP ${res.status}`);
    state.runId = r.id; render(r, fresh ? null : state.answers);
    $("results").focus({ preventScroll: true });
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) { showError(String(e.message || e)); }
  finally { $("busy").hidden = true; $("run").disabled = false; }
}

function showError(msg) { $("error").hidden = false; $("error").innerHTML = `<h2>Could not reconcile</h2><p>${esc(msg)}</p>`; }

function answeredHtml(a) {
  // After a re-run, say what the user decided, so a changed count (e.g. the other candidate now open) is explained.
  const parts = [];
  (a.pairs || []).forEach((p) => parts.push(`bank row ${[].concat(p.bank).join(" + ")} pays ledger row ${[].concat(p.ledger).join(" + ")}`));
  Object.entries(a.mapping || {}).forEach(([side, m]) => parts.push(`${side} columns: ${Object.entries(m).map(([k, v]) => `${k} = ${v}`).join(", ")}`));
  Object.entries(a.date_format || {}).forEach(([side, f]) => parts.push(`${side} dates: ${{ dmy: "day first", mdy: "month first", ymd: "year first" }[f] || f}`));
  const open = a.pairs?.length ? " Lines you did not pick stay open and are listed below." : "";
  return parts.length ? `<p><b>Re-run with your answers:</b> ${parts.map(esc).join(" · ")}.${open}</p>` : "";
}

function render(r, answered = null) {
  ["error", "summary", "questions", "answered", "totalsCard", "excCard", "fuCard", "matchCard"].forEach((id) => ($(id).hidden = true));
  if (answered && answeredHtml(answered)) { $("answered").hidden = false; $("answered").innerHTML = answeredHtml(answered); }
  $("traceCard").hidden = false;
  $("total").textContent = `· ${r.total_ms} ms total · run ${r.id}`;
  $("trace").innerHTML = r.trace.map(stepHtml).join("");
  if (r.status === "error") return showError(r.error);
  if (r.questions?.length) renderQuestions(r.questions);
  if (!r.totals) return;
  $("summary").hidden = false; $("summary").innerHTML = summaryHtml(r);
  $("totalsCard").hidden = false; $("totals").innerHTML = totalsHtml(r.totals);
  $("excCard").hidden = false;
  $("exportLink").href = `/api/runs/${encodeURIComponent(r.id)}/export.csv`;
  $("exceptions").innerHTML = r.exceptions.length ? r.exceptions.map(excHtml).join("") : "<p>No exceptions.</p>";
  if (r.followups.length) { $("fuCard").hidden = false; $("followups").innerHTML = r.followups.map(fuHtml).join(""); }
  $("matchCard").hidden = false; $("matchCount").textContent = `(${r.matches.length})`;
  $("matches").innerHTML = matchesHtml(r.matches);
}

function card(label, big, sub, tone = "") {
  return `<div class="stat ${tone}"><div class="stat-label">${esc(label)}</div><div class="stat-big">${big}</div><div class="stat-sub">${sub}</div></div>`;
}

function summaryHtml(r) {
  const o = r.overview;
  const kinds = Object.entries(o.exceptions_by_kind).map(([k, n]) => `${n} ${esc(KIND_SHORT[k] || k)}`).join(" · ") || "none";
  const overdue = Object.entries(o.overdue_by_currency).map(([c, v]) => `${esc(v)} ${esc(c)}`).join(" + ") || "none";
  const diffs = Object.entries(r.totals).map(([c, v]) => `${esc(v.net_difference)} ${esc(c)}`).join("<br>");
  return card("Matched automatically", `${o.matched_bank_lines} <span class="of">of ${o.bank_lines}</span>`,
      `bank lines, in ${o.match_groups} matches with a named rule`, "ok") +
    card("To review", `${o.exceptions}`, kinds, o.exceptions ? "warn" : "ok") +
    card("Questions for you", `${o.questions}`, o.questions ? "it stopped instead of guessing (below)" : "nothing ambiguous", o.questions ? "ask" : "") +
    card("Overdue invoices", `${o.followups}`, `reminder drafts · ${overdue}`, o.followups ? "warn" : "") +
    card("Net difference", `<span class="money">${diffs}</span>`, "bank minus ledger, per currency");
}

function stepHtml(s) {
  const { step, status, ms, ...d } = s;
  const detail = Object.entries(d).filter(([, v]) => v !== null && v !== undefined && !(typeof v === "object" && !Object.keys(v).length))
    .map(([k, v]) => `${esc(k)}: ${esc(typeof v === "object" ? JSON.stringify(v) : v)}`).join(" · ");
  return `<li><span class="pill ${esc(status)}">${esc(status)}</span> <b>${esc(step)}</b> <span class="muted">${ms} ms</span><div class="detail">${detail}</div></li>`;
}

function totalsHtml(t) {
  const keys = Object.keys(TOTAL_LABEL);
  return `<table><thead><tr><th scope="col">Currency</th>${keys.map((k) => `<th scope="col" class="num">${TOTAL_LABEL[k]}</th>`).join("")}</tr></thead><tbody>` +
    Object.entries(t).map(([c, v]) => `<tr><th scope="row">${esc(c)}</th>${keys.map((k) => `<td class="num">${esc(v[k])}</td>`).join("")}</tr>`).join("") + "</tbody></table>";
}

function source(n) {
  if (n.source === "llm") return `<span class="src ok">LLM wording · numbers verified</span>`;
  if (n.source === "llm-checked") return `<span class="src warn">LLM wording · ${esc(n.note)}</span>`;
  return `<span class="src">Template wording · ${esc(n.note || "")}</span>`;
}

function rowsTable(cards) {
  if (!cards.length) return "";
  return `<div class="scroll"><table class="rows"><thead><tr><th>side</th><th>row</th><th>date</th><th class="num">amount</th><th>ccy</th><th>name / text</th><th>ref</th></tr></thead><tbody>` +
    cards.map((c) => c.raw ? `<tr><td>${esc(c.side)}</td><td>${c.row}</td><td colspan="5">${esc(JSON.stringify(c.raw))}</td></tr>` :
      `<tr><td>${esc(c.side)}</td><td>${c.row}</td><td>${esc(c.date)}</td><td class="num">${esc(c.amount)}</td><td>${esc(c.currency)}</td><td>${esc(c.name || c.desc)}</td><td>${esc(c.ref)}</td></tr>`).join("") + "</tbody></table></div>";
}

const FACT_LABEL = { bank_amount: "Bank amount", ledger_amount: "Ledger amount", difference: "Difference (code)", basis: "Paired by",
  shared_ref: "Shared reference", days_apart: "Days apart", days_counted_from: "Days counted from", duplicate_of_row: "Same as bank row",
  amount: "Amount", currency: "Currency", name_score: "Name similarity", row: "Row" };

function factsHtml(f) {
  return `<dl class="facts">${Object.entries(f).filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `<dt>${esc(FACT_LABEL[k] || k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`;
}

function excHtml(e) {
  const n = e.narrative;
  return `<article class="exc ${esc(e.kind)}"><div class="head"><span class="kind">${esc(KIND[e.kind] || e.kind)}</span> <span class="muted">${esc(e.id)}</span> ${source(n)}</div>
    <p>${esc(n.text)}</p><p class="next">Next: ${esc(n.next_step)}</p>
    <details><summary>Evidence card</summary><div class="muted">Rule: ${esc(e.rule)}</div>
      ${factsHtml(e.facts)}${rowsTable([...e.bank, ...e.ledger])}
      ${n.removed?.length ? `<div class="removed">Removed LLM sentences (number not in evidence):<ul>${n.removed.map((s) => `<li>${esc(s)}</li>`).join("")}</ul></div>` : ""}
    </details></article>`;
}

function fuHtml(f) {
  const d = f.draft;
  const label = f.status === "draft" ? "Approve draft" : esc(f.status);
  return `<article class="fu" id="fu-${esc(f.id)}"><div class="head"><b>${esc(f.counterparty)}</b> · ${esc(f.amount)} ${esc(f.currency)} · ${f.days_overdue} days overdue
    <span class="muted">(due ${esc(f.due)} from ${esc(f.due_source)}, as of ${esc(f.as_of)})</span> ${source(d)}</div>
    <div class="mail"><div><b>Subject:</b> ${esc(d.subject)}</div><pre>${esc(d.body)}</pre></div>
    <button data-approve="${esc(f.id)}" ${f.status !== "draft" ? "disabled" : ""}>${label}</button></article>`;
}

async function approve(btn) {
  btn.disabled = true;
  const res = await fetch(`/api/runs/${encodeURIComponent(state.runId)}/followups/${encodeURIComponent(btn.dataset.approve)}/approve`, { method: "POST" });
  const r = await res.json().catch(() => ({}));
  btn.textContent = res.ok ? r.followup.status : (r.detail || `HTTP ${res.status}`);
}

function matchesHtml(ms) {
  return `<table><thead><tr><th>rule</th><th>bank rows</th><th>ledger rows</th><th class="num">amount</th><th>evidence</th></tr></thead><tbody>` + ms.map((m) =>
    `<tr><td>${esc(m.rule)}</td><td>${m.bank.map((b) => b.row).join(", ")}</td><td>${m.ledger.map((l) => l.row).join(", ")}</td>
     <td class="num">${esc(m.ledger.length === 1 ? m.ledger[0].amount : m.bank[0].amount)} ${esc(m.bank[0].currency)}</td><td class="muted">${esc(JSON.stringify(m.evidence))}</td></tr>`).join("") + "</tbody></table>";
}

function renderQuestions(qs) {
  $("questions").hidden = false;
  $("questions").innerHTML = "<h2>The agent needs you</h2><p class='muted'>It stopped instead of guessing. Your answer is re-checked by code before it is used.</p>" +
    qs.map(questionHtml).join("") + `<button id="answerBtn">Answer and re-run</button>`;
}

function questionHtml(q, i) {
  if (q.type === "column_mapping") {
    const opts = (sel) => q.headers.map((h) => `<option ${h === sel ? "selected" : ""}>${esc(h)}</option>`).join("");
    return `<fieldset class="q" data-i="${i}" data-type="column_mapping" data-side="${esc(q.side)}"><legend>${esc(q.text)}</legend>
      ${q.answer_not_used?.length ? `<p class="warn-text">Not used, the values do not fit: ${esc(q.answer_not_used.join("; "))}</p>` : ""}
      ${q.suggested && Object.keys(q.suggested).length ? `<p class="muted">LLM suggestion (pre-filled, please confirm): ${esc(q.suggestion_reason || "")}</p>` : ""}
      ${q.missing.map((r) => `<label class="inline">${esc(r)} <select data-role="${esc(r)}">${opts((q.suggested || {})[r])}</select></label>`).join(" ")}
      <div class="scroll"><table class="rows"><thead><tr>${q.headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${
        q.sample.map((r) => `<tr>${q.headers.map((h) => `<td>${esc(r[h])}</td>`).join("")}</tr>`).join("")}</tbody></table></div></fieldset>`;
  }
  if (q.type === "date_format")
    return `<fieldset class="q" data-type="date_format" data-side="${esc(q.side)}"><legend>${esc(q.text)}</legend><p class="muted">Examples: ${esc(q.examples.join(", "))}</p>
      <label class="inline"><input type="radio" name="df-${esc(q.side)}" value="dmy" checked> day first</label> <label class="inline"><input type="radio" name="df-${esc(q.side)}" value="mdy"> month first</label></fieldset>`;
  if (q.type === "ambiguous_match") {
    // Each option is a whole grouping {bank:[...], ledger:[...]}; the server re-checks that the amounts agree.
    const opts = q.combos
      ? q.combos.map((c) => q.split_side === "b" ? { bank: c, ledger: q.ledger } : { bank: q.bank, ledger: c })
      : q.ledger.length > 1 ? q.ledger.map((l) => ({ bank: [q.bank[0]], ledger: [l] }))
      : q.bank.map((b) => ({ bank: [b], ledger: [q.ledger[0]] }));
    const radios = opts.map((o) => `<label class="opt"><input type="radio" name="amb-${i}" value="${esc(JSON.stringify(o))}"> bank row ${o.bank.join(" + ")} pays ledger row ${o.ledger.join(" + ")}</label>`);
    return `<fieldset class="q" data-type="ambiguous_match" data-i="${i}"><legend>${esc(q.amount)} ${esc(q.currency)}: ${esc(q.text)}</legend>${radios.join("")}
      <label class="opt"><input type="radio" name="amb-${i}" value="" checked> leave open</label></fieldset>`;
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

document.addEventListener("click", (ev) => {
  const t = ev.target.closest("button");
  if (!t) return;
  if (t.dataset.approve) approve(t);
  else if (t.id === "answerBtn") answer();
});
readFile($("bankFile"), "bank"); readFile($("ledgerFile"), "ledger");
$("tryDemo").addEventListener("click", tryDemo);
$("run").addEventListener("click", () => run(true));
health();
loadSamples().then(() => { if (new URLSearchParams(location.search).has("demo")) tryDemo(); });
