/** The UnderCover Agent: an alien in sunglasses. It bobs while it works. */
export function AgentMark({
  size,
  working,
}: Readonly<{ size: number; working: boolean }>) {
  return (
    <svg
      className={working ? "agent-mark agent-mark-working" : "agent-mark"}
      width={size}
      height={size}
      viewBox="0 -6 48 54"
      aria-hidden="true"
    >
      <path className="mark-ink" d="M16 8 12 0M32 8l4-8" />
      <circle className="mark-bulb mark-bulb-left" cx="12" cy="-1" r="3" />
      <circle className="mark-bulb mark-bulb-right" cx="36" cy="-1" r="3" />
      <path
        className="mark-head"
        d="M24 4c12 0 20 9 20 20 0 12-10 21-20 21S4 36 4 24C4 13 12 4 24 4Z"
      />
      <path
        className="mark-shades"
        d="M7 19h34v5c0 4-3 7-7 7h-3c-3 0-5-2-6-5h-2c-1 3-3 5-6 5h-3c-4 0-7-3-7-7Z"
      />
      <path className="mark-glint" d="m12 22 4 5M31 22l4 5" />
      <path className="mark-ink mark-smile" d="M18 37q6 4 12 0" />
    </svg>
  );
}
