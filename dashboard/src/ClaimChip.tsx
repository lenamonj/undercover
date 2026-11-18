import { ViewTransition } from "react";
import { Link } from "react-router";

/** A claim's id. The queue's chip and the claim page's share a name, so it flies across. */
export function ClaimChip({
  claimId,
  linked,
}: Readonly<{ claimId: string; linked: boolean }>) {
  return (
    <ViewTransition name={`claim-${claimId}`} share="claim-fly">
      {linked ? (
        <Link className="mono claim-chip" to={`/claims/${claimId}`}>
          {claimId}
        </Link>
      ) : (
        <span className="mono claim-chip">{claimId}</span>
      )}
    </ViewTransition>
  );
}
