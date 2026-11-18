import { useEffect, useState } from "react";
import { api, type Instructions } from "./api";

export function InstructionsPage() {
  const [instructions, setInstructions] = useState<Instructions>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    api
      .getInstructions()
      .then(setInstructions)
      .catch((caught: unknown) => {
        setError(String(caught));
      });
  }, []);

  if (error) return <p role="alert">{error}</p>;
  if (!instructions) return <p>Loading the instructions</p>;

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="muted">What the UnderCover Agent is told. Read only.</p>
      <section className="panel" aria-labelledby="queue-instructions">
        <h2 id="queue-instructions">Running the queue</h2>
        <pre className="instructions">{instructions.queue}</pre>
      </section>
      <section className="panel" aria-labelledby="claim-instructions">
        <h2 id="claim-instructions">Working a claim</h2>
        <pre className="instructions">{instructions.claim}</pre>
      </section>
    </>
  );
}
