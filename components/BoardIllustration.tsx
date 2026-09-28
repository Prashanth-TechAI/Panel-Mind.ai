/**
 * The board, drawn rather than photographed.
 *
 * A stock or AI-generated photograph of five strangers reads as a stock photo
 * of five strangers — and invented faces on a page about honesty is the wrong
 * note. This is geometric on purpose: figures are abstracted to head, shoulder
 * and nameplate, so nobody is depicted and nothing is claimed.
 *
 * Each seat wears its own member accent (--color-m0…m4), the same categorical
 * palette the interview room and the scorecards use, so the illustration is
 * colour-coded to the product rather than merely decorative.
 */

/** Chairman centre and highest; the arc mirrors a real panel's seating. */
const SEATS = [
  { x: 104, headY: 224, accent: "var(--color-m1)" },
  { x: 212, headY: 212, accent: "var(--color-m2)" },
  { x: 320, headY: 196, accent: "var(--color-m0)" },
  { x: 428, headY: 212, accent: "var(--color-m3)" },
  { x: 536, headY: 224, accent: "var(--color-m4)" },
];

const TABLE_TOP = 306;

export function BoardIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 640 460"
      className={className}
      role="img"
      aria-label="An illustration of a five-member interview board seated behind a table"
    >
      <defs>
        <linearGradient id="pm-wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-accent-wash)" />
          <stop offset="100%" stopColor="var(--color-surface)" />
        </linearGradient>
        <linearGradient id="pm-table" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-accent)" />
          <stop offset="100%" stopColor="var(--color-accent-deep)" />
        </linearGradient>
        {/* Keeps every figure tucked behind the table edge. */}
        <clipPath id="pm-room">
          <rect x="0" y="0" width="640" height={TABLE_TOP} />
        </clipPath>
      </defs>

      <rect width="640" height="460" rx="28" fill="url(#pm-wall)" />

      {/* --- Backdrop: a North Block dome and colonnade, kept faint --- */}
      <g clipPath="url(#pm-room)" opacity="0.13" fill="var(--color-accent)">
        <rect x="318" y="52" width="4" height="18" rx="2" />
        <circle cx="320" cy="118" r="46" />
        <rect x="266" y="112" width="108" height="12" rx="4" />
        <rect x="250" y="160" width="140" height="10" rx="4" />
        {[262, 292, 322, 352, 382].map((x) => (
          <rect key={x} x={x} y="170" width="12" height="74" rx="4" />
        ))}
        <rect x="238" y="244" width="164" height="12" rx="4" />
      </g>

      {/* --- Soft floor shadow so the table has something to sit on --- */}
      <ellipse cx="320" cy="312" rx="290" ry="16" fill="var(--color-accent)" opacity="0.07" />

      {/* --- The five members --- */}
      <g clipPath="url(#pm-room)">
        {SEATS.map(({ x, headY, accent }) => (
          <g key={x}>
            {/* Shoulders. Reaches past the table so it is never cut short. */}
            <path
              d={`M${x - 46} ${TABLE_TOP + 20}
                  v-${TABLE_TOP + 20 - (headY + 46)}
                  a46 46 0 0 1 92 0
                  v${TABLE_TOP + 20 - (headY + 46)} Z`}
              fill={accent}
              opacity="0.9"
            />
            {/* Collar and lapel, in the page ground so it reads as a shirt. */}
            <path
              d={`M${x - 15} ${headY + 30} L${x} ${headY + 58} L${x + 15} ${headY + 30}
                  a30 30 0 0 0 -30 0 Z`}
              fill="var(--color-surface)"
            />
            <circle cx={x} cy={headY} r="27" fill="var(--color-accent)" />
            {/* A single highlight gives the head form without giving it a face. */}
            <path
              d={`M${x - 27} ${headY} a27 27 0 0 1 27 -27 v54 a27 27 0 0 1 -27 -27 Z`}
              fill="#fff"
              opacity="0.07"
            />
          </g>
        ))}
      </g>

      {/* --- The table --- */}
      <path
        d={`M40 ${TABLE_TOP + 26} Q320 ${TABLE_TOP - 20} 600 ${TABLE_TOP + 26}
            L600 ${TABLE_TOP + 34} Q320 ${TABLE_TOP - 12} 40 ${TABLE_TOP + 34} Z`}
        fill="var(--color-brass)"
      />
      <path
        d={`M40 ${TABLE_TOP + 32} Q320 ${TABLE_TOP - 14} 600 ${TABLE_TOP + 32}
            L600 424 a18 18 0 0 1 -18 18 H58 a18 18 0 0 1 -18 -18 Z`}
        fill="url(#pm-table)"
      />

      {/* --- Nameplates, the one place brass belongs --- */}
      {SEATS.map(({ x }, i) => {
        const y = TABLE_TOP + 54 + (i === 2 ? 0 : i === 0 || i === 4 ? 12 : 6);
        return (
          <g key={x}>
            <rect x={x - 34} y={y} width="68" height="16" rx="3" fill="var(--color-brass)" />
            <rect
              x={x - 26}
              y={y + 6}
              width="52"
              height="4"
              rx="2"
              fill="var(--color-accent-deep)"
              opacity="0.35"
            />
          </g>
        );
      })}

      {/* --- Papers in front of the Chairman --- */}
      <rect x="286" y={TABLE_TOP + 86} width="68" height="46" rx="4" fill="var(--color-surface)" opacity="0.92" />
      <rect x="296" y={TABLE_TOP + 96} width="48" height="3" rx="1.5" fill="var(--color-accent)" opacity="0.3" />
      <rect x="296" y={TABLE_TOP + 104} width="38" height="3" rx="1.5" fill="var(--color-accent)" opacity="0.22" />
      <rect x="296" y={TABLE_TOP + 112} width="44" height="3" rx="1.5" fill="var(--color-accent)" opacity="0.22" />
    </svg>
  );
}
