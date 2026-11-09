import React from 'react';
import { AlertTriangle, CheckCircle2, ClipboardCheck, Link2, RefreshCw, ShieldCheck } from 'lucide-react';

export default function Phase4Guidance({ guidance, loading, error, onRefresh }) {
  return <section className="phase4-panel" aria-label="Document-specific readiness and reported sources">
    <header className="phase4-heading"><h3><ClipboardCheck size={16}/> Document readiness</h3>
      <button className="review-preview" type="button" onClick={onRefresh} disabled={loading}><RefreshCw size={14}/>{loading ? 'Checking...' : 'Refresh checks'}</button>
    </header>
    <p className="phase4-disclaimer">Reported information coverage only. This is not certification of legal validity, eligibility or filing readiness.</p>
    {error && <p className="review-alert" role="alert">{error}</p>}
    {guidance && <>
      <p className="phase4-count">Document-specific details addressed: <strong>{guidance.readiness.required_answered}/{guidance.readiness.required_total}</strong></p>
      <div className="phase4-questions">{guidance.questions.filter(q=>q.required).map(q=><div key={q.key} className="phase4-question">
        {q.answered ? <CheckCircle2 size={14} color="#367d6e"/> : <AlertTriangle size={14} color="#b88435"/>}
        <span><strong>{q.label}</strong><small>{q.answered ? 'Provided — please verify' : q.question}</small></span>
      </div>)}</div>
      <details><summary>Warnings and further checks ({guidance.readiness.warnings.length})</summary>
        <ul>{guidance.readiness.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul>
      </details>
      <details><summary><Link2 size={14}/> Reported facts and evidence links ({guidance.fact_trace.length})</summary>
        <p className="phase4-disclaimer">Sources refer to statements in this conversation. They do not confirm that any evidence is authentic or legally sufficient.</p>
        {guidance.fact_trace.map(row=><div key={row.key} className="phase4-trace">
          <strong>{row.label}</strong><span>{row.value}</span>
          <small>{row.status || 'user-reported'} · unverified{row.sources.length ? ' · source recorded' : ' · independently confirm source'}</small>
        </div>)}
      </details>
    </>}
  </section>;
}

export function ArgumentOutline({ outline, loading, error, onGenerate }) {
  return <section className="phase4-panel phase4-argument" aria-label="Factual argument builder">
    <header className="phase4-heading"><h3><ShieldCheck size={16}/> Prepare your factual argument</h3>
      <button type="button" className="review-preview" onClick={onGenerate} disabled={loading}>{loading ? 'Preparing...' : outline ? 'Refresh outline' : 'Build outline'}</button>
    </header>
    <p className="phase4-disclaimer">Organizes your statements for practice. It does not predict success or prepare court submissions.</p>
    {error && <p className="review-alert" role="alert">{error}</p>}
    {outline && <div className="phase4-outline">
      <strong>Opening statement</strong><p>{outline.opening}</p>
      <strong>Points to support</strong><ol>{outline.key_points.map(point=><li key={point.label}><b>{point.label}:</b> {point.text} (reported, not verified)</li>)}</ol>
      <strong>What the other party might question</strong><ul>{outline.possible_challenges.map((point,i)=><li key={i}>{point}</li>)}</ul>
      <strong>How to respond</strong><p>{outline.response_guidance}</p>
      <strong>Suggested closing</strong><p>{outline.closing}</p>
      {!!outline.questions_to_prepare.length && <><strong>Questions to clarify</strong><ul>{outline.questions_to_prepare.map((q,i)=><li key={i}>{q}</li>)}</ul></>}
      <small>{outline.disclaimer}</small>
    </div>}
  </section>;
}
