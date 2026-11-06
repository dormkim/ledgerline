# Demo video script (target 2:30, hard limit 3:00)

Record at 1280×800 or larger, browser zoom 100%, on the **public Vultr URL** (not localhost), so the
address bar shows the deployed app. Have the Vultr console tab (Compute → the VM) open for shot 6.
Speak slowly. Lines in quotes are the voice-over, and the italic notes are on-screen actions.

---

**0:00 to 0:15. Problem**
"Every month, someone in finance puts the bank statement next to the ledger and ticks off lines one by one.
The exports never look the same, and a wrong match means a wrong close. Ledgerline is an agent that does
this work. It does the math in code and never guesses."

*Show the app home page with the URL bar visible.*

**0:15 to 0:35. Input**
"Here are two real-world-style exports: a bank statement with USD and EUR lines, and a QuickBooks-style
ledger with invoices and bills."

*Click "Load demo data". Scroll the two text boxes briefly. Click "Reconcile".*

**0:35 to 1:05. The agent's steps**
"In about two seconds it read both files, worked out which column is which, decided the date format from
the data, picked the ledger's sign convention by checking which one agrees with the bank, and matched the
lines with four named rules. Every step is listed here with its timing."

*Point at the step list: map columns, choose ledger sign, match by_rule (R1, R2, R3 split), the LLM step's ms.*

**1:05 to 1:25. It asks instead of guessing**
"One bank deposit of 750 dollars has no name and no reference, and two invoices of exactly 750 were
issued the same day. A guess would be a coin flip, so the agent stops and asks."

*Show the "The agent needs you" box. Choose "bank row 8 pays ledger row 10". Click "Answer and re-run".*

**1:25 to 1:55. Exceptions with evidence**
"Now the reviewer only sees the exceptions. Delta Freight paid 15 dollars less than invoiced, probably a
wire fee. Code computed that difference, and the model only wrote the sentence. This green tag means
every number in the sentence was checked against the evidence. If the model writes a number that isn't
in the evidence, that sentence is removed and the removal is shown here."

*Open E1's "Evidence card": rule, facts, source rows. Then point at the duplicate Cloudnine charge and the
unmatched Stripe payout.*

**1:55 to 2:15. Follow-ups with a human in the loop**
"Unpaid invoices past their due date get a reminder draft. The days overdue and the amounts come from the
ledger, not from the model. Nothing is sent until a person approves it, and every approval goes to an audit log."

*Click "Approve draft" on Ironclad Partners. The button changes to "approved".*

**2:15 to 2:35. Runs on Vultr**
"The whole backend runs on one Vultr Cloud Compute VM in a locked-down container. The model calls go to
Vultr Serverless Inference. We tested it on twenty CSV pairs that someone else wrote without seeing the
code. It scored eight out of ten on first sight in both sets, we fixed what they exposed, and every
failure and fix is in the repo."

*Show the Vultr console with the VM, then `/healthz` showing `vultr_inference: true`, then the README's evaluation section.*

**2:35 to 2:45. Close**
"Ledgerline: the code does the math, the model writes the words, and it asks when it isn't sure."

---

Before recording, check:
- [ ] `/healthz` on the public URL shows `"state":"configured"` and `"vultr_inference":true`
- [ ] Run the demo once before recording (the first call after a deploy can be slower), then reload the page
- [ ] Export as MP4, under 3 minutes
