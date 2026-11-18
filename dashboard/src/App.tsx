import { Link, NavLink, Route, Routes } from "react-router";
import { ClaimPage } from "./ClaimPage";
import { InstructionsPage } from "./InstructionsPage";
import { QueuePage } from "./QueuePage";

export function App() {
  return (
    <div className="app">
      <header className="masthead">
        <Link to="/" className="brand">
          UnderCover <span className="tagline">Claims desk</span>
        </Link>
        <nav aria-label="Main">
          <NavLink to="/" end>
            Queue
          </NavLink>
          <NavLink to="/instructions">Agent instructions</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<QueuePage />} />
          <Route path="/claims/:claimId" element={<ClaimPage />} />
          <Route path="/instructions" element={<InstructionsPage />} />
        </Routes>
      </main>
    </div>
  );
}
