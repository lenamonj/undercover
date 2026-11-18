import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, type QueueItem } from "./api";
import {
  money,
  STATUS_LABELS,
  STATUSES,
  VERDICT_LABELS,
  words,
} from "./format";
import { StatusBadge } from "./StatusBadge";

export function QueuePage() {
  const [queue, setQueue] = useState<QueueItem[]>();
  const [error, setError] = useState<string>();

  const refresh = useCallback(() => {
    api
      .listClaims()
      .then(setQueue)
      .catch((caught: unknown) => {
        setError(String(caught));
      });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const busy = queue?.some((claim) => claim.status === "in_progress") ?? false;
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(refresh, 1000);
    return () => {
      clearInterval(timer);
    };
  }, [busy, refresh]);

  async function workQueue() {
    try {
      await api.workQueue();
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
        <button
          type="button"
          onClick={() => void workQueue()}
          disabled={waiting === 0}
        >
          Work the queue
        </button>
      </div>

      <ul className="counts" aria-label="Claims by status">
        {STATUSES.map((status) => (
          <li key={status} className={`count count-${status}`}>
            <span className="count-number">
              {queue.filter((claim) => claim.status === status).length}
            </span>
            <span>{STATUS_LABELS[status]}</span>
          </li>
        ))}
      </ul>

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
              <tr key={claim.claim_id}>
                <td>
                  <Link className="mono" to={`/claims/${claim.claim_id}`}>
                    {claim.claim_id}
                  </Link>
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
