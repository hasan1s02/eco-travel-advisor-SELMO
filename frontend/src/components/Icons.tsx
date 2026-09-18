/** Inline SVG icons.
 *
 *  Icons are always decorative here (aria-hidden): every icon sits beside a
 *  text label, so a screen reader announcing it would only duplicate content.
 *  Transport mode icons carry meaning alongside the colour band, which is what
 *  keeps the interface usable for colour-blind travellers.
 */

type Props = { size?: number; className?: string };

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false as const,
});

export function LeafIcon({ size = 20 }: Props) {
  return (
    <svg {...base(size)}>
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
      <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
    </svg>
  );
}

export function SendIcon({ size = 20 }: Props) {
  return (
    <svg {...base(size)}>
      <path d="m22 2-7 20-4-9-9-4Z" />
      <path d="M22 2 11 13" />
    </svg>
  );
}

export function LocationIcon({ size = 18 }: Props) {
  return (
    <svg {...base(size)}>
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}

export function MicIcon({ size = 18 }: Props) {
  return (
    <svg {...base(size)}>
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <path d="M12 19v3" />
    </svg>
  );
}

export function AgentIcon({ size = 18 }: Props) {
  return (
    <svg {...base(size)}>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

export function WarningIcon({ size = 20 }: Props) {
  return (
    <svg {...base(size)}>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
      <path d="M12 9v4M12 17h.01" />
    </svg>
  );
}

export function InfoIcon({ size = 20 }: Props) {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  );
}

/** Transport-mode glyph, chosen by the `icon` field the action server sends. */
export function ModeIcon({ name, size = 21 }: Props & { name: string }) {
  switch (name) {
    case "train":
      return (
        <svg {...base(size)}>
          <rect x="4" y="3" width="16" height="13" rx="2" />
          <path d="M4 10h16M8 20l-2 2M16 20l2 2M9 20h6" />
          <circle cx="8.5" cy="13" r=".6" fill="currentColor" />
          <circle cx="15.5" cy="13" r=".6" fill="currentColor" />
        </svg>
      );
    case "plane":
      return (
        <svg {...base(size)}>
          <path d="M17.8 19.2 16 11l3.5-3.5a2.12 2.12 0 0 0-3-3L13 8 4.8 6.2a.5.5 0 0 0-.5.8l3.2 3.5-2 2-2.2-.5a.5.5 0 0 0-.5.8L5 15l1.7 2.2a.5.5 0 0 0 .8-.5l-.5-2.2 2-2 3.5 3.2a.5.5 0 0 0 .8-.5Z" />
        </svg>
      );
    case "bus":
      return (
        <svg {...base(size)}>
          <path d="M4 17V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v11" />
          <path d="M4 11h16M2 17h20M7 21v-2M17 21v-2" />
        </svg>
      );
    case "car":
      return (
        <svg {...base(size)}>
          <path d="M5 17h14M6.5 17V9.5L8 6h8l1.5 3.5V17" />
          <path d="M4 12h16" />
          <circle cx="8" cy="17.5" r="1.5" />
          <circle cx="16" cy="17.5" r="1.5" />
        </svg>
      );
    case "ferry":
      return (
        <svg {...base(size)}>
          <path d="M3 18a3 3 0 0 0 3-2 3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 3 2" />
          <path d="M4 14 6 8h12l2 6M12 8V4M8 4h8" />
        </svg>
      );
    case "bike":
      return (
        <svg {...base(size)}>
          <circle cx="6" cy="17" r="3.5" />
          <circle cx="18" cy="17" r="3.5" />
          <path d="M6 17 10 8h4l4 9M9 8h6M14 8l2 4" />
        </svg>
      );
    case "walk":
      return (
        <svg {...base(size)}>
          <circle cx="13" cy="4" r="1.8" />
          <path d="M11 21l2-5-2-3V9l3-1 2 3 2 1M11 13l-2 8" />
        </svg>
      );
    default:
      return <LeafIcon size={size} />;
  }
}
