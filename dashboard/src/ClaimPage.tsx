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
import { ClaimChip } from "./ClaimChip";
import {
  ClaimDetails,
  DecisionPanel,
  HistoryPanel,
  PolicyPanel,
  SectionsRead,
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
  // The head renders from the URL at once, so the claim's chip can fly in
  // from the queue while the claim itself loads.
  return (
    <>
      <Link className="back" to="/">
        Back to the queue
      </Link>
      <div className="page-head">
        <h1>
          <ClaimChip claimId={claimId} linked={false} /> {claim?.summary}
        </h1>
        {claim && <StatusBadge status={claim.status} />}
      </div>
      {claim ? (
        <ClaimBody
          claim={claim}
          steps={steps}
          context={context}
          onRun={() => {
            act(() => api.runAgent(claimId));
          }}
          onSignOff={(handlerId) => {
            act(() => api.signOff(claimId, handlerId));
          }}
        />
      ) : (
        <p>Loading the claim</p>
      )}
    </>
  );
}

function ClaimBody({
  claim,
  steps,
  context,
  onRun,
  onSignOff,
}: Readonly<{
  claim: Claim;
  steps: Step[];
  context: Context | undefined;
  onRun: () => void;
  onSignOff: (handlerId: string) => void;
}>) {
  return (
    <>
      {claim.status === "waiting" && !claim.running && (
        <button type="button" className="launch" onClick={onRun}>
          Run the agent
        </button>
      )}
      <div className="claim-grid">
        <div className="column">
          <DecisionPanel claim={claim} />
          {claim.status === "awaiting_sign_off" && context && (
            <SignOffForm handlers={context.handlers} onSignOff={onSignOff} />
          )}
          <SectionsRead steps={steps} />
          <StepsPanel steps={steps} working={claim.running} />
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
