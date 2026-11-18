import { ViewTransition } from "react";
import { Link, NavLink, Route, Routes } from "react-router";
import { AgentMark } from "./AgentMark";
import { ClaimPage } from "./ClaimPage";
import { InstructionsPage } from "./InstructionsPage";
import { QueuePage } from "./QueuePage";

export function App() {
  return (
    <div className="app">
      <header className="masthead">
        <Link to="/" className="brand">
          <AgentMark size={40} working={false} />
          <span className="brand-name">UnderCover</span>
          <span className="tagline">Claims desk</span>
        </Link>
        <nav aria-label="Main">
          <NavLink to="/" end>
            Queue
          </NavLink>
          <NavLink to="/instructions">Agent instructions</NavLink>
        </nav>
      </header>
      {/* Page changes animate: the router navigates inside a React Transition. */}
      <ViewTransition default="page">
        <main>
          <Routes>
            <Route path="/" element={<QueuePage />} />
            <Route path="/claims/:claimId" element={<ClaimPage />} />
            <Route path="/instructions" element={<InstructionsPage />} />
          </Routes>
        </main>
      </ViewTransition>
    </div>
  );
}
