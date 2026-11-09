import React from 'react';
import { AlertTriangle, BookOpen, CheckCircle2, ClipboardCheck, Download, ExternalLink, Scale, ShieldAlert } from 'lucide-react';

export default function LegalPlanPanel({
  plan, checked, onCheck, reviewed, onReviewed, onExport, exporting, error, onRefresh, refreshing,
}) {
  if (!plan) return <section className="legal-plan"><div className="case-heading"><h2>Your personalized action plan</h2><p>Describe a fictional civil dispute to generate source-linked general guidance.</p></div></section>;
  const completeCount = plan.actions.filter(a => checked[a.id] === true).length;
  const available = new Set(plan.sources.map(s => s.id));
  const sourceLabels = Object.fromEntries(plan.sources.map(s => [s.id, s.title]));
  return <section className="legal-plan">
    <div className="case-heading">
      <h2>Legal position & next steps</h2>
      <p>Case: {plan.case_id || 'Current session'} · Source review: {plan.source_reviewed_on}</p>
    </div>
    {plan.escalation.level !== 'general_guidance' && <div className="legal-warning" role="alert">
      <ShieldAlert size={20}/>
      <div><strong>{plan.escalation.level === 'urgent_review' ? 'Prompt professional help recommended' : 'Category needs review'}</strong>
        <p>{plan.escalation.message}</p>
      </div>
    </div>}
    <div className="legal-position">
      <div className="legal-title"><Scale size={17}/><h3>Where you may stand</h3></div>
      <strong>{plan.position.heading}</strong>
      <p>{plan.position.explanation}</p>
      <ul>{plan.position.considerations.map((note,i)=><li key={i}>{note}</li>)}</ul>
      <small>{plan.position.status}</small>
    </div>
    <div className="legal-section">
      <h3>Potentially relevant law & official sources</h3>
      {plan.statute_references.length ? plan.statute_references.map(item=><div className="legal-reference" key={item.source_id}>
        <strong>{item.title}</strong><p>{item.applicability}</p>
      </div>) : <p className="case-muted">No specific law identified reliably for this case type. Avoid assuming a statute applies.</p>}
      <div className="legal-sources">
        {plan.sources.map(source=><a href={source.url} key={source.id} target="_blank" rel="noopener noreferrer">
          <BookOpen size={15}/>
          <span><strong>{source.title}</strong><small>{source.relevance}</small></span>
          <ExternalLink size={14}/>
        </a>)}
      </div>
      <p className="case-muted">{plan.source_status}</p>
    </div>
    <div className="legal-section">
      <h3>Reported support, limitations & evidence gaps</h3>
      <strong className="legal-subtitle">Reported supporting information — not verified legal strengths</strong>
      <ul>{plan.supporting_reports.map((item,i)=><li key={i}>{item}</li>)}</ul>
      <strong className="legal-subtitle">Unknowns and possible weaknesses</strong>
      <ul>{plan.uncertainties.map((item,i)=><li key={i}>{item}</li>)}</ul>
      <strong className="legal-subtitle">Missing details or documents</strong>
      <ul>{plan.evidence_gaps.length ? plan.evidence_gaps.map((item,i)=><li key={i}>{item}</li>) : <li>No gaps flagged by these limited checks; verification may still be required.</li>}</ul>
    </div>
    <div className="legal-section">
      <h3>Where you could take action</h3>
      <p className="case-muted">These are possible channels, not instructions to file, and no eligibility has been confirmed.</p>
      {plan.routes.map(route=><div className="legal-route" key={route.id}><strong>{route.title}</strong><p>{route.when_to_consider}</p>
        <small>{route.eligibility_status}</small>
        {!!route.source_ids.length && <div className="legal-route-links">Sources: {route.source_ids.filter(id => available.has(id)).map((id,i)=><span key={id}>{i>0?', ':''}{sourceLabels[id]}</span>)}</div>}
      </div>)}
    </div>
    <div className="legal-section">
      <div className="legal-title"><ClipboardCheck size={17}/><h3>Personalized action checklist</h3></div>
      <p className="case-muted">Mark tasks completed only after you carry them out. Progress does not mean legal compliance.</p>
      <div className="legal-progress" role="status">{completeCount}/{plan.actions.length} tasks marked complete</div>
      {plan.actions.map((task,i)=><label className="legal-task" key={task.id}>
        <input type="checkbox" checked={checked[task.id] === true} onChange={e=>onCheck(task.id,e.target.checked)}/>
        <span><strong>{i+1}. {task.title}</strong><small>{task.instructions}</small></span>
      </label>)}
    </div>
    <div className="legal-warning legal-warning-light">
      <AlertTriangle size={19}/>
      <div><strong>Urgency & lawyer escalation</strong><p>{plan.escalation.message}</p>
        <ul>{plan.escalation.reasons.map((reason,i)=><li key={i}>{reason}</li>)}</ul>
      </div>
    </div>
    <div className="legal-export">
      <label><input type="checkbox" checked={reviewed} onChange={e=>onReviewed(e.target.checked)}/>
        <span>I have reviewed this informational action plan. I understand that source links do not prove legal applicability and this PDF is not ready for filing.</span>
      </label>
      <div className="legal-buttons">
        <button type="button" className="case-secondary" onClick={onRefresh} disabled={refreshing}>Refresh plan from case facts</button>
        <button type="button" onClick={onExport} disabled={!reviewed||exporting}><Download size={15}/> {exporting?'Generating…':'Download action plan PDF'}</button>
      </div>
      {error && <p className="voice-alert" role="alert">{error}</p>}
      <p className="case-muted">{plan.disclaimer}</p>
    </div>
  </section>;
}
