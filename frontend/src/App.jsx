import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowRight, BookOpen, CheckCircle2, ChevronRight, CircleHelp, ClipboardList,
  Download, ExternalLink, FileDown, FileText, Info, Landmark, LoaderCircle,
  MessageCircle, RotateCcw, Scale, Send, ShieldAlert, ShieldCheck, Sparkles,
  UserRound, Wallet, Building2, House, Menu, X,
} from 'lucide-react';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const options = [
  { value: 'auto', label: 'Auto-detect', icon: Sparkles },
  { value: 'property', label: 'Property & rental', icon: House },
  { value: 'consumer', label: 'Consumer & refunds', icon: Wallet },
  { value: 'employment', label: 'Employment & salary', icon: Building2 },
  { value: 'contract', label: 'Contract & payments', icon: FileText },
];
const fieldConfig = [
  ['location', 'City / state', 'e.g. Kanpur, Uttar Pradesh'],
  ['counterparty', 'Other party', 'e.g. landlord / company'],
  ['amount', 'Amount in dispute', 'e.g. ₹25,000'],
  ['event_date', 'Important date', 'e.g. 2 October 2026'],
  ['evidence', 'Evidence available', 'e.g. receipts, emails, agreement'],
  ['desired_resolution', 'What you want', 'e.g. full refund / unpaid salary'],
];
const sampleCases = [
  { text: 'My landlord has not returned my ₹25,000 deposit after I moved out of my rented flat. I have a rental agreement and bank-transfer proof.', label: 'Rental deposit' },
  { text: 'I ordered a laptop online for ₹48,000. It arrived damaged, and the seller has not responded to my refund requests. I have the order invoice.', label: 'Online refund' },
  { text: 'My employer has not paid two months of my salary after I resigned. I have payslips, my offer letter and email reminders.', label: 'Unpaid salary' },
  { text: 'A client has not paid my ₹30,000 invoice even though I completed the agreed website project. I have an email agreement and proof of delivery.', label: 'Client payment' },
];
const initialMessages = [{ role: 'assistant', content: "Hello! I'm CaseWise AI. Describe an everyday civil dispute in your own words. I'll help organize the facts, identify missing details and suggest cautious next steps." }];
const emptyProfile = Object.fromEntries(fieldConfig.map(([key]) => [key, '']));

function LabelPill({ icon: Icon, children }) {
  return <span className="label-pill"><Icon size={13} />{children}</span>;
}

export default function App() {
  const [category, setCategory] = useState('auto');
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState('');
  const [profile, setProfile] = useState(emptyProfile);
  const [analysis, setAnalysis] = useState(null);
  const [tab, setTab] = useState('summary');
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [draftProfile, setDraftProfile] = useState({ ...emptyProfile, sender_name: '', sender_contact: '' });
  const [draftFacts, setDraftFacts] = useState('');
  const [draftConfirmed, setDraftConfirmed] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const bottom = useRef(null);
  const textarea = useRef(null);
  const sentMessages = messages.filter(m => m.role === 'user');

  useEffect(() => {
    fetch(`${API_BASE}/api/health`).then(r => r.ok ? r.json() : Promise.reject()).then(setApiStatus).catch(() => setApiStatus({ status: 'offline' }));
  }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, busy]);

  async function callAnalyze(next, addReply = true, formProfile = profile, formCategory = category) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: next, category: formCategory, profile: formProfile }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Analysis request failed.');
      setAnalysis(data);
      if (addReply) setMessages([...next, { role: 'assistant', content: data.assistant_message }]);
    } catch (e) { setError(e.message || 'Could not connect to the backend.'); }
    finally { setBusy(false); }
  }

  function onSend(event) {
    event?.preventDefault();
    const value = input.trim();
    if (!value || busy) return;
    const next = [...messages, { role: 'user', content: value }];
    setMessages(next);
    setInput('');
    callAnalyze(next);
  }
  function refresh() {
    if (!sentMessages.length || busy) return;
    callAnalyze(messages, false);
  }
  function reset() {
    setMessages(initialMessages); setInput(''); setAnalysis(null); setProfile(emptyProfile);
    setCategory('auto'); setError(''); setTab('summary'); setReviewOpen(false); setDraftConfirmed(false);
  }
  function openDraftReview() {
    if (!analysis || analysis.needs_lawyer || busy) return;
    // Prefer an explicit correction in Case details over auto-detected text.
    const autoFields = analysis.profile_used || {};
    setDraftProfile({ ...emptyProfile, ...autoFields, ...Object.fromEntries(Object.entries(profile).filter(([, value]) => value?.trim())), sender_name: '', sender_contact: '' });
    setDraftFacts(analysis.summary.draft_facts || '');
    setDraftConfirmed(false);
    setReviewError('');
    setReviewOpen(true);
  }
  const essentialFields = ['counterparty', 'location', 'event_date', 'desired_resolution'];
  const draftMissing = essentialFields.filter(key => !draftProfile[key]?.trim());

  async function downloadDraft() {
    if (!sentMessages.length || downloading || analysis?.needs_lawyer || !draftConfirmed || draftMissing.length || !draftFacts.trim()) return;
    setDownloading(true); setError(''); setReviewError('');
    try {
      const safeProfile = { ...draftProfile, facts_narrative: draftFacts };
      const response = await fetch(`${API_BASE}/api/draft`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, category, profile: safeProfile, confirmed: true }),
      });
      if (!response.ok) {
        const details = await response.json();
        throw new Error(details.detail || 'Could not generate draft.');
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = 'CaseWise-AI-Reviewed-Draft.pdf';
      link.click();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
      setProfile(draftProfile);
      setReviewOpen(false);
      await callAnalyze(messages, false, draftProfile, category);
    } catch (e) { setReviewError(e.message || 'PDF download failed.'); }
    finally { setDownloading(false); }
  }

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><div className="brand-symbol"><Scale size={23} strokeWidth={2}/></div><div><div className="brand-title">CaseWise <span>AI</span></div><div className="brand-caption">Civil guidance, made clearer.</div></div></div>
      <div className="topbar-right"><div className="topbar-meta"><ShieldCheck size={15}/> Designed for cautious guidance</div><div className={`status-pill ${apiStatus?.status === 'ok' ? 'online' : 'offline'}`}><span className="status-dot"/>{apiStatus?.status === 'ok' ? 'Backend connected' : 'Backend unavailable'}</div></div>
      <button className="mobile-menu" aria-label="Toggle case details" onClick={() => setMobileOpen(v => !v)}>{mobileOpen ? <X size={22}/> : <Menu size={22}/>}</button>
    </header>
    <main className="workspace">
      <section className="left-panel">
        <div className="intro">
          <div className="eyebrow"><span className="small-line"/> YOUR CIVIL LEGAL COMPANION</div>
          <h1>Make sense of your <em>legal situation.</em></h1>
          <p>Tell us what's happening. We'll help you map out the facts, understand potential next steps, and prepare a draft request for resolution.</p>
          <div className="intro-pills"><LabelPill icon={ShieldCheck}>Source-linked</LabelPill><LabelPill icon={ClipboardList}>Case summaries</LabelPill><LabelPill icon={FileText}>PDF drafts</LabelPill></div>
        </div>
        <div className="chat-card">
          <div className="chat-heading"><div><div className="chat-icon"><MessageCircle size={17}/></div><div><strong>Case conversation</strong><small>{analysis ? `${analysis.summary.category_label} · ${analysis.mode === 'gemini-assisted' ? 'AI-assisted intake' : 'Guided demo mode'}` : 'Start by describing your dispute'}</small></div></div><button className="ghost-action" title="Start a new conversation" onClick={reset}><RotateCcw size={15}/> <span>Reset</span></button></div>
          <div className="category-bar"><span>Type of issue</span><div className="category-select-wrap"><select aria-label="Select civil dispute category" value={category} onChange={e => setCategory(e.target.value)}>{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select><ChevronRight size={14}/></div></div>
          <div className="chat-stream" aria-live="polite">
            {messages.map((m,i) => <div className={`chat-message ${m.role}`} key={i}>{m.role === 'assistant' && <div className="chat-avatar"><Scale size={15}/></div>}<div className="chat-content"><div className="chat-speaker">{m.role === 'assistant' ? 'CASEWISE AI' : 'YOU'}</div><p>{m.content}</p></div></div>)}
            {busy && <div className="chat-message assistant"><div className="chat-avatar"><Scale size={15}/></div><div className="chat-content"><div className="chat-speaker">CASEWISE AI</div><p className="loading-text"><LoaderCircle size={14} className="spin"/> Reviewing the facts...</p></div></div>}
            {messages.length === 1 && <div className="samples"><span>Or try an example</span><div className="sample-list">{sampleCases.map(s => <button key={s.label} onClick={() => { setInput(s.text); textarea.current?.focus(); }}>{s.label}<ArrowRight size={13}/></button>)}</div></div>}
            <div ref={bottom}/>
          </div>
          <form className="composer" onSubmit={onSend}><textarea ref={textarea} value={input} rows={2} maxLength={2000} placeholder="Describe what happened, when, and what outcome you want..." onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}/><div className="composer-footer"><span><Info size={13}/> Do not enter sensitive personal identifiers</span><button type="submit" disabled={!input.trim() || busy} className="send-button">Send <Send size={15}/></button></div></form>
        </div>
        <div className="footnote"><ShieldAlert size={15}/> CaseWise AI is a demonstration tool, not a lawyer. Check all advice and legal deadlines with a professional.</div>
      </section>
      <aside className={`right-panel ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="right-tabs"><button className={tab === 'summary' ? 'active' : ''} onClick={() => setTab('summary')}><ClipboardList size={16}/> Case overview</button><button className={tab === 'details' ? 'active' : ''} onClick={() => setTab('details')}><UserRound size={16}/> Case details</button></div>
        <div className="right-content">
          {tab === 'summary' ? <>
            <div className="panel-topline"><span>YOUR CASE FILE</span>{analysis && <span className="category-tag">{analysis.summary.category_label}</span>}</div>
            {!analysis ? <div className="empty-overview"><div className="empty-circle"><BookOpen size={32} strokeWidth={1.6}/></div><h3>Your case starts here</h3><p>Share your situation in the chat. A structured summary, possible next steps, and source links will appear here.</p><button onClick={() => textarea.current?.focus()}>Describe your case <ArrowRight size={14}/></button></div> : <>
              <div className="section-block"><h2>What you've told us</h2><p className="issue-text">{analysis.summary.issue}</p></div>
              {Object.keys(analysis.summary.facts_reported).length > 0 && <div className="section-block"><h2>Facts captured</h2><dl className="facts-list">{Object.entries(analysis.summary.facts_reported).map(([k,v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></div>}
              <div className="section-block"><div className="section-header"><h2>Suggested next steps</h2><span className="subtle-label">General information</span></div><ol className="steps-list">{analysis.next_steps.map((v,i) => <li key={i}><span className="step-number">{i+1}</span><span>{v}</span></li>)}</ol></div>
              <div className="section-block"><div className="section-header"><h2>Information still needed</h2><button className="inline-button" onClick={() => setTab('details')}>Add details <ChevronRight size={13}/></button></div>{analysis.summary.missing_details.length ? <div className="missing-tags">{analysis.summary.missing_details.map(v => <span key={v}>{v}</span>)}</div> : <p className="small-success"><CheckCircle2 size={15}/> Basic fields supplied. More facts may still be required.</p>}</div>
              <div className="section-block"><h2>Official starting points</h2><div className="source-list">{analysis.sources.map(src => <a key={src.id} href={src.url} target="_blank" rel="noopener noreferrer"><span className="source-icon"><Landmark size={16}/></span><span><strong>{src.title}</strong><small>{src.description}</small></span><ExternalLink size={14}/></a>)}</div><p className="source-caveat">{analysis.source_status}</p></div>
              <div className="safety-card"><ShieldAlert size={17}/><div><strong>Know the limits</strong>{analysis.safety_flags.map((flag,i) => <p key={i}>{flag}</p>)}</div></div>
              <div className="draft-card"><div className="draft-icon"><FileDown size={20}/></div><div><strong>Draft a resolution request</strong><p>Review your collected facts, fill missing details, and confirm before creating the PDF.</p></div><button disabled={downloading || analysis.needs_lawyer || busy} onClick={openDraftReview}><ClipboardList size={16}/> Review &amp; generate PDF</button></div>
            </>}
          </> : <div className="details-tab"><div className="panel-topline">OPTIONAL FACT CHECK</div><h2>Complete your case details</h2><p>Add only details you're comfortable sharing. These fields are used to create a clearer summary and draft letter.</p><div className="profile-fields">{fieldConfig.map(([key,label,hint]) => <label key={key}>{label}<input value={profile[key]} maxLength={250} placeholder={hint} onChange={e => setProfile(p => ({ ...p, [key]: e.target.value }))}/></label>)}</div><button className="update-button" disabled={!sentMessages.length || busy} onClick={async () => { await callAnalyze(messages, false); setTab('summary'); }}>Update case overview <ArrowRight size={16}/></button><p className="privacy-note"><ShieldCheck size={15}/> Case text is not intentionally saved on the server. If Gemini is configured, conversational inputs are sent to its API.</p></div>}
          {error && <div className="error-box" role="alert"><ShieldAlert size={16}/> {error}</div>}
        </div>
      </aside>
    </main>
    {reviewOpen && <div className="review-overlay" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget && !downloading) setReviewOpen(false); }}>
      <section className="review-dialog" role="dialog" aria-modal="true" aria-labelledby="review-heading">
        <div className="review-top"><div><span className="panel-topline">BEFORE YOU DOWNLOAD</span><h2 id="review-heading">Review your draft details</h2><p>Information suggested by the chat may be incomplete. Correct any facts below. The draft is a factual request, not a formal legal notice.</p></div><button type="button" className="review-close" aria-label="Close review" onClick={() => setReviewOpen(false)} disabled={downloading}><X size={19}/></button></div>
        <div className="review-body">
          <label className="review-label">Your factual account (editable)<textarea rows={5} maxLength={1200} value={draftFacts} onChange={e => { setDraftFacts(e.target.value); setDraftConfirmed(false); }}/><small>Remove any chatbot questions or claims you cannot verify. Only your confirmed wording will enter the letter.</small></label>
          <div className="review-grid">{fieldConfig.map(([key,label,hint]) => <label className="review-label" key={key}>{label}{essentialFields.includes(key) && <span className="field-required"> Required</span>}<input value={draftProfile[key] || ''} maxLength={250} placeholder={hint} onChange={e => { setDraftProfile(p => ({ ...p, [key]: e.target.value })); setDraftConfirmed(false); }}/></label>)}</div>
          <div className="review-grid">{[['sender_name','Your name (optional)'],['sender_contact','Your contact details (optional)']].map(([key,label]) => <label className="review-label" key={key}>{label}<input value={draftProfile[key] || ''} maxLength={180} placeholder="Leave blank to use a placeholder" onChange={e => { setDraftProfile(p => ({ ...p, [key]: e.target.value })); setDraftConfirmed(false); }}/></label>)}</div>
          {draftMissing.length > 0 && <p className="review-alert"><ShieldAlert size={16}/> Complete {draftMissing.map(key => fieldConfig.find(([k]) => k === key)?.[1]).join(', ')} before generating. If a date is genuinely unknown, write “Not known” rather than guessing.</p>}
          <label className="review-confirm"><input type="checkbox" checked={draftConfirmed} onChange={e => setDraftConfirmed(e.target.checked)}/> <span>I have reviewed the narrative and confirmed the details I supplied. I understand this is a preliminary letter and must be checked before sending.</span></label>
          {reviewError && <p className="review-alert" role="alert">{reviewError}</p>}
        </div>
        <div className="review-actions"><button type="button" className="review-cancel" onClick={() => setReviewOpen(false)} disabled={downloading}>Cancel</button><button type="button" className="review-download" onClick={downloadDraft} disabled={downloading || !draftConfirmed || draftMissing.length > 0 || !draftFacts.trim()}>{downloading ? <LoaderCircle size={16} className="spin"/> : <Download size={16}/>} Generate reviewed PDF</button></div>
      </section>
    </div>}
    <footer className="site-footer"><span>© 2026 CaseWise AI · Built as an explainable civil-guidance prototype</span><span>Not legal advice · India-focused</span></footer>
  </div>;
}
