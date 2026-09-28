/**
 * Line icons.
 *
 * Drawn rather than typed: emoji render differently on every platform and read
 * as placeholder work. These inherit currentColor and sit on a 24px grid.
 */

const base = {
  width: 22,
  height: 22,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export function IconBoard(props: { className?: string }) {
  return (
    <svg {...base} {...props}>
      <circle cx="7" cy="8" r="2.2" />
      <circle cx="17" cy="8" r="2.2" />
      <circle cx="12" cy="6.5" r="2.4" />
      <path d="M3 18c0-2.3 1.8-4 4-4s4 1.7 4 4M13 18c0-2.3 1.8-4 4-4s4 1.7 4 4" />
    </svg>
  );
}

export function IconForm(props: { className?: string }) {
  return (
    <svg {...base} {...props}>
      <path d="M6 3h9l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </svg>
  );
}

export function IconMic(props: { className?: string }) {
  return (
    <svg {...base} {...props}>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}

export function IconChart(props: { className?: string }) {
  return (
    <svg {...base} {...props}>
      <path d="M4 20V5M4 20h16" />
      <path d="M8 16v-4M12 16V8M16 16v-6M20 16v-9" />
    </svg>
  );
}

export function IconTarget(props: { className?: string }) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" r="1" fill="currentColor" />
    </svg>
  );
}

export function IconShield(props: { className?: string }) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3Z" />
      <path d="M9.5 12l1.8 1.8L15 10" />
    </svg>
  );
}

export function IconClock(props: { className?: string }) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

export function IconLayers(props: { className?: string }) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3l9 5-9 5-9-5 9-5Z" />
      <path d="M3 13l9 5 9-5M3 17l9 5 9-5" />
    </svg>
  );
}
