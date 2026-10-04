import { useId, useState } from "react";

export function InfoPopover({ label, children }: { label: string; children: string }) {
  const [pinned, setPinned] = useState(false);
  const descriptionId = useId();

  return (
    <span className={`info-popover ${pinned ? "info-popover--pinned" : ""}`}>
      <button
        type="button"
        className="info-popover-trigger"
        aria-label={label}
        aria-describedby={descriptionId}
        aria-expanded={pinned}
        onClick={() => setPinned((value) => !value)}
      >
        i
      </button>
      <span className="info-popover-panel" id={descriptionId} role="note">
        {children}
      </span>
    </span>
  );
}
