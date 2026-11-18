import { useEffect, useState } from "react";
import { api } from "./api";

export function InstructionsPage() {
  const [instructions, setInstructions] = useState<string>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    api
      .getInstructions()
      .then((response) => {
        setInstructions(response.instructions);
      })
      .catch((caught: unknown) => {
        setError(String(caught));
      });
  }, []);

  if (error) return <p role="alert">{error}</p>;

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="muted">
        What the UnderCover Agent is told before every claim. Read only.
      </p>
      <pre className="panel instructions">
        {instructions ?? "Loading the instructions"}
      </pre>
    </>
  );
}
