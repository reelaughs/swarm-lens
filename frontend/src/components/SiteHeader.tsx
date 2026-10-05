import type { MouseEvent } from "react";

interface Props {
  label?: string;
  homeHref: string;
  onHome: () => void;
}

export function SiteHeader({ label, homeHref, onHome }: Props) {
  const navigateHome = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onHome();
  };

  return (
    <header className="site-header">
      <div className="brand-lockup">
        <a className="brand" href={homeHref} onClick={navigateHome}>SwarmLens</a>
        <span className="tagline">What changed the swarm?</span>
      </div>
      <div className="header-meta" aria-label="Project context">
        <span>AI Village</span>
        <span>Retrospective forensics</span>
        {label && <span className="pipeline-badge">{label}</span>}
      </div>
    </header>
  );
}
