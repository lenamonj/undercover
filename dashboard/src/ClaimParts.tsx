import { useState } from "react";
import { AgentMark } from "./AgentMark";
import type { Claim, ClaimHistory, Handler, Policy, Step } from "./api";
import { money, VERDICT_LABELS, words } from "./format";

function paymentText(claim: Claim): string {
  if (claim.paid_amount !== null) return `Paid ${money(claim.paid_amount)}`;
  if (claim.status === "awaiting_sign_off") {
    return "Waits for a handler's sign-off";
  }
  return "Not paid";
}

export function DecisionPanel({ claim }: Readonly<{ claim: Claim }>) {
  if (!claim.decision) return null;
  return (
    <section
      className={`panel decision decision-${claim.decision}`}
      aria-labelledby="decision-heading"
    >
      <h2 id="decision-heading">Decision</h2>
      <div className="verdict">
        <span className="stamp">{VERDICT_LABELS[claim.decision]}</span>
        <span className="payout">{money(claim.payout ?? 0)}</span>
      </div>
      <dl className="facts">
        <dt>Payment</dt>
        <dd>{paymentText(claim)}</dd>
        {claim.signed_off_by && (
          <>
            <dt>Signed off by</dt>
            <dd>{claim.signed_off_by}</dd>
          </>
        )}
        <dt>Policy section</dt>
        <dd>{claim.policy_section}</dd>
      </dl>
      <p className="reason">{claim.reason}</p>
    </section>
  );
}

export function SignOffForm({
  handlers,
  onSignOff,
}: Readonly<{
  handlers: Handler[];
  onSignOff: (handlerId: string) => void;
}>) {
  const [handlerId, setHandlerId] = useState("");
  return (
    <form
      className="panel sign-off"
      onSubmit={(event) => {
        event.preventDefault();
        onSignOff(handlerId);
      }}
    >
      <h2>Sign-off</h2>
      <p>This payout is over $1,000.00. A handler must sign off to pay it.</p>
      <label>
        Handler
        <select
          value={handlerId}
          onChange={(event) => {
            setHandlerId(event.target.value);
          }}
          required
        >
          <option value="">Choose a handler</option>
          {handlers.map((handler) => (
            <option key={handler.handler_id} value={handler.handler_id}>
              {handler.name}
            </option>
          ))}
        </select>
      </label>
      <button type="submit">Sign off and pay</button>
    </form>
  );
}

const STEP_LABELS: Record<Step["kind"], string> = {
  tool_call: "Calls",
  tool_result: "Result",
  read: "Read",
  reply: "Agent",
  error: "Error",
};

export function StepsPanel({
  steps,
  working,
}: Readonly<{
  steps: Step[];
  working: boolean;
}>) {
  return (
    <section className="panel" aria-labelledby="steps-heading">
      <div className="steps-head">
        <h2 id="steps-heading">Agent steps</h2>
        <AgentMark size={36} working={working} />
      </div>
      {steps.length === 0 && (
        <p className="muted">
          {working ? "The agent is starting" : "The agent has not run yet."}
        </p>
      )}
      <ol className="steps">
        {steps.map((step) => (
          <li key={step.step_id} className={`step step-${step.kind}`}>
            <span className="step-kind">{STEP_LABELS[step.kind]}</span>
            <span className="step-detail">{step.detail}</span>
          </li>
        ))}
      </ol>
      {working && steps.length > 0 && <p className="working">Working</p>}
    </section>
  );
}

export function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <section className="panel" aria-labelledby="claim-heading">
      <h2 id="claim-heading">The claim</h2>
      <dl className="facts">
        <dt>Type</dt>
        <dd>{words(claim.claim_type)}</dd>
        <dt>Incident</dt>
        <dd>
          {claim.incident_date}, {claim.incident_location}
        </dd>
        <dt>Submitted</dt>
        <dd>{claim.submitted_on}</dd>
        {claim.attempts > 0 && (
          <>
            <dt>Failed attempts</dt>
            <dd>{claim.attempts}</dd>
          </>
        )}
      </dl>
      <blockquote className="story bubble bubble-customer">
        {claim.story}
      </blockquote>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Category</th>
            <th className="number">Amount</th>
          </tr>
        </thead>
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td>{words(item.category)}</td>
              <td className="number">{money(item.amount)}</td>
            </tr>
          ))}
          <tr className="total">
            <td>Total claimed</td>
            <td />
            <td className="number">{money(claim.amount_claimed)}</td>
          </tr>
        </tbody>
      </table>
      <h3>Documents</h3>
      {claim.documents.map((document) => (
        <details key={document.name} className="document">
          <summary>{document.name}</summary>
          <p>{document.content}</p>
        </details>
      ))}
    </section>
  );
}

export function PolicyPanel({ policy }: Readonly<{ policy: Policy }>) {
  const addOns = policy.add_on_details.map((addOn) => addOn.name).join(", ");
  return (
    <section className="panel" aria-labelledby="policy-heading">
      <h2 id="policy-heading">Policy</h2>
      <dl className="facts">
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Plan</dt>
        <dd>{policy.plan_details.name}</dd>
        <dt>Add-ons</dt>
        <dd>{addOns || "None"}</dd>
        <dt>Bought</dt>
        <dd>{policy.purchased_on}</dd>
        <dt>Trip</dt>
        <dd>
          {policy.trip.destination}, {policy.trip.departs_on} to{" "}
          {policy.trip.returns_on}
        </dd>
        <dt>Trip cost</dt>
        <dd className="mono">{money(policy.trip.trip_cost)}</dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
      </dl>
    </section>
  );
}

export function HistoryPanel({ history }: Readonly<{ history: ClaimHistory }>) {
  return (
    <section className="panel" aria-labelledby="history-heading">
      <h2 id="history-heading">Claim history</h2>
      <p className="muted">
        {history.name}, a customer since {history.customer_since}
      </p>
      {history.previous_claims.length === 0 && <p>No earlier claims.</p>}
      <ul className="history">
        {history.previous_claims.map((earlier) => (
          <li key={earlier.claim_id}>
            <span className="mono">{earlier.claim_id}</span> {earlier.filed_on}:{" "}
            {earlier.summary}. {words(earlier.outcome)},{" "}
            {money(earlier.amount_paid)} paid.
          </li>
        ))}
      </ul>
    </section>
  );
}

export function SectionsRead({ steps }: Readonly<{ steps: Step[] }>) {
  const reads = steps.filter((step) => step.kind === "read");
  return (
    <section className="panel" aria-labelledby="sections-heading">
      <h2 id="sections-heading">Sections read</h2>
      {reads.length === 0 && <p className="muted">None yet.</p>}
      <ul className="chips">
        {reads.map((step) => (
          <li
            key={step.step_id}
            className={
              step.detail.startsWith("Claims manual")
                ? "chip chip-manual"
                : "chip chip-wording"
            }
          >
            {step.detail}
          </li>
        ))}
      </ul>
    </section>
  );
}
