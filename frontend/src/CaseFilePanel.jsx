import React from 'react';
import { AlertTriangle, CheckCircle2, Download, FileText, Plus, ShieldCheck, Trash2 } from 'lucide-react';

const EXTRA_FIELDS = [
  ['user_role', 'Your role', 'e.g. Tenant, Customer, Employee'],
  ['key_event', 'Key event', 'Describe the central event'],
];
const SUBTYPE_OPTIONS = {
  property: [['rental_deposit','Rental deposit'],['eviction','Possession / eviction'],['repairs','Repairs'],['ownership','Ownership / title']],
  consumer: [['refund','Refund dispute'],['defective_product','Defective product'],['delivery','Delivery issue'],['service','Service complaint']],
  employment: [['unpaid_salary','Unpaid salary'],['final_settlement','Final settlement'],['contract_terms','Employment terms']],
  contract: [['unpaid_invoice','Unpaid invoice'],['breach','Contract performance'],['advance','Advance payment']],
};

function LabelValue({label,children}) {
  return <div className="casefield"><strong>{label}</strong><div>{children}</div></div>;
}

export default function CaseFilePanel({
  mode, file, profile, onProfile, corrections, onCorrection,
  timelineEdits, onTimeline, evidenceEdits, onEvidence,
  story, onStory, contextCorrections, onContext, reviewed, onReviewed, resolvedIssues, onResolve,
  onRefresh, onExport, exportBusy, saving, error,
}) {
  if (!file) return <div className="empty-overview"><h3>Build your case first</h3><p>Describe your civil dispute in the chat. Your case file will appear here.</p></div>;

  const timeline = timelineEdits === null ? file.timeline : timelineEdits;
  const evidence = evidenceEdits === null ? file.evidence : evidenceEdits;
  const readiness = file.completeness;
  const unresolved = file.issues.filter(issue => !resolvedIssues.includes(issue.id));
  const editTimeline = (index, field, value) => onTimeline(timeline.map((item,i) => i===index ? {...item,[field]:value} : item));
  const editEvidence = (index, field, value) => onEvidence(evidence.map((item,i) => i===index ? {...item,[field]:value} : item));

  if (mode==='timeline') return <section className="case-builder">
    <div className="case-heading"><h2>Case timeline</h2><p>Events are user-reported. Dates without a reliable calendar value are not guessed or assigned to the wrong event.</p></div>
    {timeline.length ? timeline.map((event,i) => <div className="case-edit-card" key={event.id || i}>
      <div className="case-edit-top"><strong>{event.event_kind === "ongoing_status" ? "Ongoing status" : "Event"} {i+1}</strong><span>{event.status === 'ai_suggested' ? 'AI suggested — review' : event.status === 'user_edited' ? 'User edited' : 'User reported'}</span></div>
      <label>Date <input value={event.date || ''} placeholder="Exact date, relative date, or unknown" maxLength={80} onChange={e=>editTimeline(i,'date',e.target.value)}/></label>
      <label>What happened? <textarea value={event.event || ''} maxLength={500} rows={3} onChange={e=>editTimeline(i,'event',e.target.value)}/></label>
      <div className="case-edit-bottom"><small>{Number.isInteger(event.source_message) ? 'Conversation entry '+(event.source_message+1) : 'Added manually or suggested — not verified'}</small><button type="button" onClick={()=>onTimeline(timeline.filter((_,j)=>j!==i))}><Trash2 size={14}/> Remove</button></div>
    </div>) : <p className="case-muted">No dated events yet. Add the first reported event.</p>}
    <button className="case-secondary" onClick={()=>onTimeline([...timeline,{id:'manual-'+Date.now(),date:'',event:'',source_message:null,source_excerpt:'',status:'user_edited'}])}><Plus size={15}/> Add event</button>
    <div className="case-actions"><button disabled={saving} onClick={onRefresh}>Save timeline changes</button></div>
  </section>;

  if (mode==='evidence') return <section className="case-builder">
    <div className="case-heading"><h2>Evidence & proof tracker</h2><p>Listed evidence is not independently checked. Indicate only whether you say you have the document; no file upload is required.</p></div>
    {evidence.length ? evidence.map((item,i) => <div className="case-edit-card" key={item.id || i}>
      <div className="case-edit-top"><strong>{item.type || 'Evidence'}</strong><span>Not independently verified</span></div>
      <label>Description <input value={item.description || ''} maxLength={300} onChange={e=>editEvidence(i,'description',e.target.value)}/></label>
      <label>Availability
        <select value={item.availability || 'unknown'} onChange={e=>editEvidence(i,'availability',e.target.value)}>
          <option value="mentioned">Mentioned, not confirmed available</option>
          <option value="user_says_available">I say I have it</option>
          <option value="user_says_unavailable">I do not have it</option>
          <option value="unknown">Not sure</option>
        </select>
      </label>
      <div className="case-edit-bottom"><small>{Number.isInteger(item.source_message) ? 'Conversation entry '+(item.source_message+1) : 'User added; authenticity not checked'}</small><button onClick={()=>onEvidence(evidence.filter((_,j)=>j!==i))}><Trash2 size={14}/> Remove</button></div>
    </div>) : <p className="case-muted">No proof identified yet. You may add evidence you have mentioned or want to preserve.</p>}
    <button className="case-secondary" onClick={()=>onEvidence([...evidence,{id:'new-evidence-'+Date.now(),type:'Other',description:'',availability:'unknown',source_message:null}])}><Plus size={15}/> Add evidence</button>
    <div className="case-actions"><button disabled={saving} onClick={onRefresh}>Save evidence changes</button></div>
  </section>;

  return <section className="case-builder">
    <div className="case-heading"><h2>Review & export case file</h2><p>Correct suggested facts, review possible inconsistencies and confirm the narrative. Exporting is not a legal filing.</p></div>
    <div className="case-completeness">
      <div className="case-meter-top"><strong>Information collected</strong><span>{readiness.completed}/{readiness.total} checks ({readiness.percent}%)</span></div>
      <div className="case-meter" role="progressbar" aria-valuenow={readiness.completed} aria-valuemin={0} aria-valuemax={readiness.total}><span style={{width:readiness.percent+'%'}}/></div>
      <p>{readiness.description}</p>
      <div className="case-checklist">{readiness.checks.map(item=><div key={item.key} className={item.complete?'complete':''}>{item.complete?<CheckCircle2 size={14}/>:<span className="case-unchecked"/>}{item.label}</div>)}</div>
    </div>
    <div className="case-edit-card">
      <h3>Case identification</h3>
      <LabelValue label="Category">{file.category_label}</LabelValue>
      <label>Specific dispute subtype
        <select value={corrections.subtype ?? file.subtype.code ?? ''} onChange={e=>onCorrection('subtype',e.target.value)}>
          <option value="">Not specified</option>
          {(SUBTYPE_OPTIONS[file.category] || []).map(([id,label])=><option key={id} value={id}>{label}</option>)}
        </select>
      </label>
      {EXTRA_FIELDS.map(([key,label,hint])=><label key={key}>{label}<input maxLength={500} value={corrections[key] ?? file.facts[key]?.value ?? ''} placeholder={hint} onChange={e=>onCorrection(key,e.target.value)}/></label>)}
      {[
        ['counterparty','Other party'],['location','City / State'],['event_date','Relevant date'],['amount','Amount involved'],['evidence','Evidence status'],['desired_resolution','Requested resolution'],
      ].map(([key,label])=><label key={key}>{label}<input maxLength={250} value={profile[key] || ''} placeholder={file.facts[key]?.value || 'Not supplied'} onChange={e=>onProfile(key,e.target.value)}/><small>Current case value: {file.facts[key]?.value || 'Not supplied'}</small></label>)}
    </div>
    <div className="case-edit-card">
      <h3>Additional case-specific questions</h3>
      <p>These prompts adapt to the dispute type. “Not known” is valid; do not guess. You can also answer in the chat.</p>
      {(file.context?.questions || []).length ? file.context.questions.map(item=><label key={item.id}>
        {item.label}<small>{item.question}</small>
        <textarea rows={2} maxLength={500} value={contextCorrections[item.id] ?? item.answer ?? ''}
          placeholder="Your answer, or 'Not known'"
          onChange={e=>onContext(item.id,e.target.value)}/>
      </label>) : <p className="case-muted">No additional questions for this case type yet.</p>}
    </div>
    <div className="case-edit-card">
      <h3>Compiled case facts (reported, not verified)</h3>
      <dl className="facts-list">{(file.structured_summary?.items || []).map(item=><div key={item.key}>
        <dt>{item.label}</dt><dd>{item.value}</dd>
      </div>)}</dl>
      <p className="case-muted">This is assembled from structured fields; it does not change your own narrative or verify documents.</p>
    </div>
    <div className="case-edit-card">
      <h3>Editable factual summary</h3>
      <p>Only user-confirmed text should be included in final documents. AI-generated wording is a suggestion, not an established fact.</p>
      <textarea rows={7} maxLength={1400} value={story} onChange={e=>onStory(e.target.value)} placeholder="Describe the dispute in your own words."/>
    </div>
    <div className="case-edit-card">
      <h3>Possible inconsistencies & missing information</h3>
      {file.missing.length > 0 && <p className="case-muted">Basic information not yet supplied: {file.missing.map(m=>m.label).join(', ')}</p>}
      {(file.context?.questions || []).some(q=>q.status === 'missing') && <p className="case-muted">Further dispute-specific details to clarify: {file.context.questions.filter(q=>q.status==='missing').map(q=>q.label).join(', ')}. These do not change the basic 8-field score.</p>}
      {file.issues.length===0 && <p className="case-muted">No obvious amount/date discrepancy detected by this limited check. Other inconsistencies may still exist.</p>}
      {file.issues.map(issue=><div className="case-issue" key={issue.id}>
        <AlertTriangle size={16}/><div><strong>{issue.type==='possible_conflict'?'Potential inconsistency':'Needs clarification'}</strong><p>{issue.message}</p><small>Values: {issue.examples.join(' | ')}</small>
          <label className="case-check"><input type="checkbox" checked={resolvedIssues.includes(issue.id)} onChange={e=>onResolve(issue.id,e.target.checked)}/> I have reviewed this issue</label>
        </div>
      </div>)}
      {unresolved.length>0 && <p className="case-muted">Unresolved review flags: {unresolved.length}. You may still export with warnings shown.</p>}
    </div>
    <div className="case-confirm">
      <label><input type="checkbox" checked={reviewed} onChange={e=>onReviewed(e.target.checked)}/> <span>I have checked the narrative and information entered in this case file. I understand that this is not verification of evidence or legal advice.</span></label>
    </div>
    <div className="case-actions">
      <button className="case-secondary" disabled={saving} onClick={onRefresh}>Save changes</button>
      <button disabled={!reviewed||!story.trim()||exportBusy} onClick={()=>onExport('pdf')}><Download size={16}/> Export PDF</button>
      <button disabled={!reviewed||!story.trim()||exportBusy} onClick={()=>onExport('json')}><FileText size={16}/> Export JSON</button>
    </div>
    {error && <p role="alert" className="voice-alert">{error}</p>}
    <p className="case-muted"><ShieldCheck size={14}/> Case data remains in the current browser session; exports are delivered without intentionally storing your case on the server.</p>
  </section>;
}
