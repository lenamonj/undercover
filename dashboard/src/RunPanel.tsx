import type { Run, Todo } from "./api";

const TODO_LABELS: Record<Todo["status"], string> = {
  pending: "To do",
  in_progress: "In progress",
  done: "Done",
  left_for_handler: "Left for a handler",
};

const RUN_LABELS: Record<Run["status"], string> = {
  running: "Running",
  finished: "Finished",
  failed: "Failed",
  interrupted: "Interrupted",
};

export function RunPanel({ run }: Readonly<{ run: Run }>) {
  return (
    <section className="panel" aria-labelledby="run-heading">
      <div className="run-head">
        <h2 id="run-heading">Run {run.run_id}</h2>
        <span className={`badge run-${run.status}`}>
          {RUN_LABELS[run.status]}
        </span>
      </div>
      <p className="muted">
        {run.claims_started} of up to {run.cap} claims started
      </p>
      {run.todos.length === 0 && (
        <p className="muted">The agent has not written its to-do list yet.</p>
      )}
      <ol className="todos" aria-label="To-do list">
        {run.todos.map((todo) => (
          <li key={todo.content} className={`todo todo-${todo.status}`}>
            <span className="todo-status">{TODO_LABELS[todo.status]}</span>
            <span>{todo.content}</span>
          </li>
        ))}
      </ol>
      {run.summary && <p className="summary">{run.summary}</p>}
      {run.error && <p role="alert">{run.error}</p>}
    </section>
  );
}
