import type { Hypothesis, SocialProcessEvaluation } from "../data/types";
import { titleCase } from "../lib/format";
import { investigatorText } from "../lib/presentationLanguage";

function HypothesisDetail({ hypothesis }: { hypothesis: Hypothesis }) {
  return (
    <article className="hypothesis">
      <div className="hypothesis-role">
        {hypothesis.interpretation_role === "best_supported_candidate"
          ? "Best-supported candidate"
          : "Plausible alternative"}
      </div>
      <h3>{hypothesis.display_name}</h3>
      <p>{investigatorText(hypothesis.summary)}</p>
      <div className="interpretation-metrics">
        <div>
          <span>Confidence</span>
          <strong>{titleCase(hypothesis.displayed_confidence)}</strong>
        </div>
        <div>
          <span>Evidence diversity</span>
          <strong>{titleCase(hypothesis.evidence_diversity)}</strong>
        </div>
      </div>
      {hypothesis.correlated_evidence_caveat && (
        <p className="correlation-note">{investigatorText(hypothesis.correlated_evidence_caveat)}</p>
      )}
      <div className="hypothesis-section">
        <h4>Evidence patterns supporting this hypothesis</h4>
        <ul>
          {hypothesis.supported_signatures.map((signature) => (
            <li key={signature.signature_id}>
              <strong>{titleCase(signature.signature_id)}</strong>
              <span>{investigatorText(signature.rationale)}</span>
              <code>{signature.evidence_ids.join(" · ")}</code>
            </li>
          ))}
        </ul>
      </div>
      <div className="hypothesis-section">
        <h4>Evidence groups</h4>
        {hypothesis.evidence_groups.map((group) => (
          <div className="evidence-group" key={group.group_id}>
            <strong>{investigatorText(group.summary)}</strong>
            <p>{investigatorText(group.independence_rationale)}</p>
          </div>
        ))}
      </div>
      <div className="status-grid">
        <div>
          <h4>Unknown signatures</h4>
          {hypothesis.unknown_signature_ids.length ? (
            <ul>{hypothesis.unknown_signature_ids.map((value) => <li key={value}>{titleCase(value)}</li>)}</ul>
          ) : <p>None recorded.</p>}
        </div>
        <div>
          <h4>Contradicted signatures</h4>
          {hypothesis.contradicted_counter_signatures.length ? (
            <ul>{hypothesis.contradicted_counter_signatures.map((value) => <li key={value.counter_signature_id}>{investigatorText(value.rationale)}</li>)}</ul>
          ) : <p>None recorded.</p>}
        </div>
      </div>
      <div className="hypothesis-section">
        <h4>Alternative explanations</h4>
        {hypothesis.alternative_explanations.length ? (
          <ul>{hypothesis.alternative_explanations.map((value) => <li key={value.summary}>{investigatorText(value.summary)}</li>)}</ul>
        ) : <p>None recorded.</p>}
      </div>
    </article>
  );
}

export function SocialProcessPanel({ evaluation }: { evaluation: SocialProcessEvaluation }) {
  if (evaluation.result === "no_clear_social_process_match") {
    return (
      <section className="social-process">
        <div className="section-label">04 · Possible social process</div>
        <h3>No clear social-process match</h3>
        <p>{investigatorText(evaluation.rationale)}</p>
      </section>
    );
  }
  return (
    <section className="social-process">
      <div className="section-label">04 · Possible social process</div>
      <p className="process-disclaimer">Interpretive candidate, not a cause of the detected transition.</p>
      {evaluation.hypotheses.map((hypothesis) => (
        <HypothesisDetail key={hypothesis.hypothesis_id} hypothesis={hypothesis} />
      ))}
      {evaluation.comparative_rationale && (
        <div className="comparative-rationale">
          <h4>Comparative rationale</h4>
          <p>{investigatorText(evaluation.comparative_rationale.statement)}</p>
        </div>
      )}
    </section>
  );
}
