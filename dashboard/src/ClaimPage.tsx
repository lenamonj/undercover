import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import {
  api,
  type Claim,
  type ClaimHistory,
  type Handler,
  type Policy,
  type Step,
} from "./api";
import {
  ClaimDetails,
  DecisionPanel,
  HistoryPanel,
  PolicyPanel,
  SignOffForm,
  StepsPanel,
} from "./ClaimParts";
import { StatusBadge } from "./StatusBadge";

interface Context {
  policy: Policy;
  history: ClaimHistory;
  handlers: Handler[];
}

export function ClaimPage() {
  const { claimId = "" } = useParams();
  const [claim, setClaim] = useState<Claim>();
  const [steps, setSteps] = useState<Step[]>([]);
  const [context, setContext] = useState<Context>();
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    const [latest, latestSteps] = await Promise.all([
      api.getClaim(claimId),
      api.listSteps(claimId),
    ]);
    setClaim(latest);
    setSteps(latestSteps);
  }, [claimId]);

  const act = useCallback(
    (action: () => Promise<unknown>) => {
      action()
        .then(refresh)
        .catch((caught: unknown) => {
          setError(String(caught));
        });
    },
    [refresh],
  );

  useEffect(() => {
    act(() => Promise.resolve());
  }, [act]);

  const policyId = claim?.policy_id;
  const customerId = claim?.customer_id;
  useEffect(() => {
    if (!policyId || !customerId) return;
    Promise.all([
      api.getPolicy(policyId),
      api.getClaimHistory(customerId),
      api.listHandlers(),
    ])
      .then(([policy, history, handlers]) => {
        setContext({ policy, history, handlers });
      })
      .catch((caught: unknown) => {
        setError(String(caught));
      });
  }, [policyId, customerId]);

  const working = claim?.running ?? false;
  useEffect(() => {
    if (!working) return;
    const timer = setInterval(() => {
      act(() => Promise.resolve());
    }, 1000);
    return () => {
      clearInterval(timer);
    };
  }, [working, act]);

  if (error) return <p role="alert">{error}</p>;
  if (!claim) return <p>Loading the claim</p>;

  return (
    <>
      <Link to="/">Back to the queue</Link>
      <div className="page-head">
        <h1>
          <span className="mono">{claim.claim_id}</span> {claim.summary}
        </h1>
        <StatusBadge status={claim.status} />
      </div>
      {claim.status === "waiting" && !claim.running && (
        <button
          type="button"
          onClick={() => {
            act(() => api.runAgent(claimId));
          }}
        >
          Run the agent
        </button>
      )}
      <div className="claim-grid">
        <div className="column">
          <DecisionPanel claim={claim} />
          {claim.status === "awaiting_sign_off" && context && (
            <SignOffForm
              handlers={context.handlers}
              onSignOff={(handlerId) => {
                act(() => api.signOff(claimId, handlerId));
              }}
            />
          )}
          <StepsPanel steps={steps} working={working} />
        </div>
        <div className="column">
          <ClaimDetails claim={claim} />
          {context && <PolicyPanel policy={context.policy} />}
          {context && <HistoryPanel history={context.history} />}
        </div>
      </div>
    </>
  );
}
