import { useCallback, useEffect, useState } from "react";
import { api, type QueueItem, type Run } from "./api";
import { ClaimChip } from "./ClaimChip";
import {
  money,
  STATUS_LABELS,
  STATUSES,
  VERDICT_LABELS,
  words,
} from "./format";
import { RunPanel } from "./RunPanel";
import { StatusBadge } from "./StatusBadge";

const DEFAULT_CAP = 5;

export function QueuePage() {
  const [queue, setQueue] = useState<QueueItem[]>();
  const [run, setRun] = useState<Run | null>(null);
  const [cap, setCap] = useState(DEFAULT_CAP);
  const [error, setError] = useState<string>();

  const refresh = useCallback(() => {
    Promise.all([api.listClaims(), api.getCurrentRun()])
      .then(([claims, current]) => {
        setQueue(claims);
        setRun(current);
      })
      .catch((caught: unknown) => {
        setError(String(caught));
      });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const running = run?.status === "running";
  const busy = running || (queue?.some((claim) => claim.running) ?? false);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(refresh, 1000);
    return () => {
      clearInterval(timer);
    };
  }, [busy, refresh]);

  async function workQueue() {
    try {
      await api.startRun(cap);
      refresh();
    } catch (caught) {
      setError(String(caught));
    }
  }

  if (error) return <p role="alert">{error}</p>;
  if (!queue) return <p>Loading the queue</p>;

  const waiting = queue.filter((claim) => claim.status === "waiting").length;

  return (
    <>
      <div className="page-head">
        <h1>Claims queue</h1>
        <div className="run-controls">
          <label>
            Claims to work
            <input
              type="number"
              min={1}
              max={queue.length}
              value={cap}
              onChange={(event) => {
                setCap(Math.max(1, Number(event.target.value)));
              }}
            />
          </label>
          <button
            type="button"
            onClick={() => void workQueue()}
            disabled={waiting === 0 || running}
          >
            Work the queue
          </button>
        </div>
      </div>

      <ul className="counts" aria-label="Claims by status">
        {STATUSES.map((status) => {
          const count = queue.filter((c) => c.status === status).length;
          return (
            <li
              key={status}
              className={`count count-${status}`}
              data-active={count > 0}
            >
              {/* The key restarts the pop animation when the number changes. */}
              <span key={count} className="count-number">
                {count}
              </span>
              <span className="count-label">{STATUS_LABELS[status]}</span>
            </li>
          );
        })}
      </ul>

      {run && <RunPanel run={run} />}

      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Customer</th>
              <th>Type</th>
              <th className="number">Claimed</th>
              <th>Status</th>
              <th>Decision</th>
              <th className="number">Payout</th>
            </tr>
          </thead>
          <tbody>
            {queue.map((claim) => (
              <tr key={claim.claim_id} data-running={claim.running}>
                <td>
                  <ClaimChip claimId={claim.claim_id} linked />
                </td>
                <td>{claim.customer_name}</td>
                <td>{words(claim.claim_type)}</td>
                <td className="number">{money(claim.amount_claimed)}</td>
                <td>
                  <StatusBadge status={claim.status} />
                </td>
                <td>{claim.decision ? VERDICT_LABELS[claim.decision] : ""}</td>
                <td className="number">
                  {claim.payout === null ? "" : money(claim.payout)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
