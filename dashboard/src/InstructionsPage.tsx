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
      <h2>Running the queue</h2>
      <pre className="panel instructions">{instructions.queue}</pre>
      <h2>Working a claim</h2>
      <pre className="panel instructions">{instructions.claim}</pre>
    </>
  );
}
