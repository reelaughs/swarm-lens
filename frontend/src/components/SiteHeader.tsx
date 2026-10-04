interface Props {
  label: string;
}

export function SiteHeader({ label }: Props) {
  return (
    <header className="site-header">
      <div className="brand-lockup">
        <span className="brand">SwarmLens</span>
        <span className="tagline">What changed the swarm?</span>
      </div>
      <div className="header-meta" aria-label="Project context">
        <span>AI Village</span>
        <span>Retrospective forensics</span>
        <span className="pipeline-badge">{label}</span>
      </div>
    </header>
  );
}
