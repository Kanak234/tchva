/**
 * Icons — a small line set drawn to one grid (24px, 1.75 stroke).
 *
 * These replace the emoji the UI used to lean on. Emoji render
 * differently on every Android build, break at small sizes, and are
 * read aloud by screen readers as their unicode name, which in Hindi
 * comes out as nonsense. Strokes render identically everywhere.
 */
type P = { size?: number; className?: string };

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
});

/** Warning — a triangle. Used for the alerts tab. */
export const IconAlert = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M12 4 2.6 20h18.8L12 4Z" />
    <path d="M12 10v4.5" />
    <path d="M12 17.4h.01" />
  </svg>
);

/** Speech — asking a question. */
export const IconAsk = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M20 4H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3v4l4.5-4H20a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1Z" />
    <path d="M8.5 10h7" />
  </svg>
);

/** A sheaf of grain — the farm. */
export const IconCrop = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M12 21V9" />
    <path d="M12 12c0-2.8-1.6-5-4-5 0 2.8 1.6 5 4 5Z" />
    <path d="M12 12c0-2.8 1.6-5 4-5 0 2.8-1.6 5-4 5Z" />
    <path d="M12 17c0-2.4-1.4-4.2-3.4-4.2 0 2.4 1.4 4.2 3.4 4.2Z" />
    <path d="M12 17c0-2.4 1.4-4.2 3.4-4.2 0 2.4-1.4 4.2-3.4 4.2Z" />
  </svg>
);

/** Shield — the "kavach" mark. */
export const IconShield = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M12 3 4.5 6v5.6c0 4.3 3 8.2 7.5 9.4 4.5-1.2 7.5-5.1 7.5-9.4V6L12 3Z" />
  </svg>
);

export const IconCheck = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M4.5 12.5 9.5 17.5 19.5 7" />
  </svg>
);

export const IconArrowLeft = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M19 12H5" />
    <path d="m11 6-6 6 6 6" />
  </svg>
);

export const IconChevron = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);

export const IconRefresh = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M20.5 12a8.5 8.5 0 1 1-2.6-6.1" />
    <path d="M20.5 4.5V10H15" />
  </svg>
);

export const IconSend = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M4 12 20.5 4 13.5 20.5 11.5 13 4 12Z" />
  </svg>
);

export const IconThumbUp = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M7 10.5 11 3a2.4 2.4 0 0 1 2.4 2.4V9.5h4.9a1.8 1.8 0 0 1 1.75 2.25l-1.6 6.4A2 2 0 0 1 16.5 19.7H7" />
    <path d="M7 10.5v9.2H4.6a1 1 0 0 1-1-1v-7.2a1 1 0 0 1 1-1H7Z" />
  </svg>
);

export const IconThumbDown = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M17 13.5 13 21a2.4 2.4 0 0 1-2.4-2.4V14.5H5.7a1.8 1.8 0 0 1-1.75-2.25l1.6-6.4A2 2 0 0 1 7.5 4.3H17" />
    <path d="M17 13.5V4.3h2.4a1 1 0 0 1 1 1v7.2a1 1 0 0 1-1 1H17Z" />
  </svg>
);

export const IconSignOut = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M14.5 16.5v2a1.5 1.5 0 0 1-1.5 1.5H5.5A1.5 1.5 0 0 1 4 18.5v-13A1.5 1.5 0 0 1 5.5 4H13a1.5 1.5 0 0 1 1.5 1.5v2" />
    <path d="M9.5 12h11" />
    <path d="m17.5 8.5 3.5 3.5-3.5 3.5" />
  </svg>
);

/** Google's G, in its brand colours. Sign-in buttons must use the real mark. */
export const IconGoogle = ({ size = 18 }: P) => (
  <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden>
    <path
      fill="#4285F4"
      d="M45.1 24.5c0-1.6-.1-2.8-.4-4.1H24v7.4h12.1c-.2 2-1.6 5-4.5 7l-.1.3 6.5 5 .5.1c4.1-3.8 6.6-9.5 6.6-15.7Z"
    />
    <path
      fill="#34A853"
      d="M24 46c5.9 0 10.9-2 14.5-5.3l-6.9-5.4c-1.8 1.3-4.3 2.2-7.6 2.2-5.8 0-10.7-3.8-12.5-9.1l-.3 0-6.7 5.2-.1.3C7.9 41 15.4 46 24 46Z"
    />
    <path
      fill="#FBBC05"
      d="M11.5 28.4c-.5-1.4-.7-2.9-.7-4.4s.3-3 .7-4.4v-.3l-6.8-5.3-.2.1A22 22 0 0 0 2 24c0 3.5.9 6.9 2.5 9.9l7-5.5Z"
    />
    <path
      fill="#EA4335"
      d="M24 10.5c4.1 0 6.9 1.8 8.5 3.3l6.2-6C34.9 4.3 29.9 2 24 2 15.4 2 7.9 7 4.5 14.1l7 5.5c1.8-5.3 6.7-9.1 12.5-9.1Z"
    />
  </svg>
);
