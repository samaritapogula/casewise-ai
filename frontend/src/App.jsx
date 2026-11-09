import React, { useEffect, useRef, useState } from 'react';
import { createContinuousSpeech } from './continuousSpeech';
import CaseFilePanel from './CaseFilePanel';
import LegalPlanPanel from './LegalPlanPanel';
import {
  ArrowRight, BookOpen, CheckCircle2, ChevronRight, CircleHelp, ClipboardList,
  Download, ExternalLink, FileDown, FileText, Info, Landmark, LoaderCircle,
  MessageCircle, RotateCcw, Scale, Send, ShieldAlert, ShieldCheck, Sparkles,
  UserRound, Wallet, Building2, House, Menu, X, Mic, MicOff, MessageSquareText,
} from 'lucide-react';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const options = [
  { value: 'auto', label: 'Auto-detect', icon: Sparkles },
  { value: 'property', label: 'Property & rental', icon: House },
  { value: 'consumer', label: 'Consumer & refunds', icon: Wallet },
  { value: 'employment', label: 'Employment & salary', icon: Building2 },
  { value: 'contract', label: 'Contract & payments', icon: FileText },
];
const DEFAULT_WELCOME = "Hello! I'm CaseWise AI. Describe an everyday civil dispute in your own words. I'll help organize the facts and ask about missing details.";
const documentTypes = [{value:'request',label:'Resolution request'}, {value:'notice',label:'Notice outline (lawyer review)'}, {value:'complaint',label:'Complaint draft'}, {value:'reply',label:'Reply draft'}, {value:'application',label:'Application for assistance'}];
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
const initialMessages = [{ role: 'assistant', content: DEFAULT_WELCOME }];
const emptyProfile = Object.fromEntries(fieldConfig.map(([key]) => [key, '']));

function LabelPill({ icon: Icon, children }) {
  return <span className="label-pill"><Icon size={13} />{children}</span>;
}

export default function App() {
  const [category, setCategory] = useState('auto');
  const [listening, setListening] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [transcriptDraft, setTranscriptDraft] = useState('');
  const [transcriptInterim, setTranscriptInterim] = useState('');
  const [voiceError, setVoiceError] = useState('');
  const [speechStatus, setSpeechStatus] = useState('');
  const speechRef = useRef(null);
  const [documentType, setDocumentType] = useState('request');
  const [argument, setArgument] = useState('');
  const [practiceResult, setPracticeResult] = useState(null);
  const [practicing, setPracticing] = useState(false);
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
  const [caseCorrections, setCaseCorrections] = useState({});
  const [caseTimelineEdits, setCaseTimelineEdits] = useState(null);
  const [caseEvidenceEdits, setCaseEvidenceEdits] = useState(null);
  const [caseStory, setCaseStory] = useState('');
  const [storyTouched, setStoryTouched] = useState(false);
  const [caseReviewed, setCaseReviewed] = useState(false);
  const [askedFields, setAskedFields] = useState([]);
  const [resolvedIssues, setResolvedIssues] = useState([]);
  const [caseExportBusy, setCaseExportBusy] = useState(false);
  const [caseError, setCaseError] = useState('');
  const [completedActions, setCompletedActions] = useState({});
  const [planReviewed, setPlanReviewed] = useState(false);
  const [planExporting, setPlanExporting] = useState(false);
  const [planError, setPlanError] = useState('');
  const caseId = useRef('CW-' + Math.random().toString(36).slice(2, 11).toUpperCase());
  const sentMessages = messages.filter(m => m.role === 'user');

  function casePayload(nextMessages = messages, other = {}) {
    return {
      messages: nextMessages,
      profile,
      category,
      case_id: caseId.current,
      case_overrides: caseCorrections,
      timeline_edits: caseTimelineEdits,
      evidence_edits: caseEvidenceEdits,
      asked_fields: askedFields,
      resolved_issues: resolvedIssues,
      story_override: storyTouched ? caseStory : '',
      reviewed: caseReviewed,
      ai_suggestion: analysis?.summary?.ai_extracted_case || null,
      completed_actions: completedActions,
      plan_reviewed: planReviewed,
      ...other,
    };
  }

  function markCaseChanged() {
    setCaseReviewed(false);
    setPlanReviewed(false);
    setCaseError('');
    setPlanError('');
  }

  async function saveCaseEdits() {
    if (!sentMessages.length || busy) return;
    setBusy(true);
    setCaseError('');
    try {
      const result = await fetch(API_BASE + '/api/case-file', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(casePayload()),
      });
      const data = await result.json();
      if (!result.ok) throw new Error(data.detail || 'Could not update the case file.');
      const followup = await fetch(API_BASE + '/api/legal-plan', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(casePayload()),
      });
      const updatedPlan = followup.ok ? await followup.json() : null;
      setAnalysis(current => current ? {...current, case_file:data, legal_plan:updatedPlan || current.legal_plan} : current);
    } catch (err) { setCaseError(err.message || 'Could not update the case file.'); }
    finally { setBusy(false); }
  }

  async function refreshLegalPlan() {
    if (!sentMessages.length || busy) return;
    setBusy(true); setPlanError('');
    try {
      const response = await fetch(API_BASE + '/api/legal-plan', {
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(casePayload()),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Unable to refresh legal guidance.');
      setAnalysis(current=>current?{...current,legal_plan:data}:current);
    } catch(err) {setPlanError(err.message || 'Unable to refresh legal guidance.');}
    finally {setBusy(false);}
  }

  async function downloadLegalPlan() {
    if (!sentMessages.length || !planReviewed || planExporting) return;
    setPlanExporting(true);setPlanError('');
    try {
      const response=await fetch(API_BASE+'/api/legal-plan/export',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(casePayload(messages,{plan_reviewed:true})),
      });
      if (!response.ok) {
        const data=await response.json();
        throw new Error(data.detail || 'Could not generate action plan PDF.');
      }
      const blob=await response.blob();
      const url=URL.createObjectURL(blob);
      const a=document.createElement('a');
      a.href=url;a.download='CaseWise-AI-Action-Plan.pdf';a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1500);
    } catch(err) {setPlanError(err.message || 'Could not generate action plan PDF.');}
    finally {setPlanExporting(false);}
  }

  async function exportCase(format) {
    if (!sentMessages.length || !caseReviewed || !caseStory.trim() || caseExportBusy) return;
    setCaseExportBusy(true);
    setCaseError('');
    try {
      const res = await fetch(API_BASE + '/api/case-export', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(casePayload(messages, {story_override:caseStory, reviewed:true, export_format:format})),
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Could not export the case file.');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'CaseWise-Case-File.' + format;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
    } catch (err) { setCaseError(err.message || 'Could not export the case file.'); }
    finally { setCaseExportBusy(false); }
  }


  useEffect(() => {
    fetch(`${API_BASE}/api/health`).then(r => r.ok ? r.json() : Promise.reject()).then(setApiStatus).catch(() => setApiStatus({ status: 'offline' }));
  }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, busy]);
  useEffect(() => () => { speechRef.current?.cancel(); }, []);

  async function callAnalyze(next, addReply = true, formProfile = profile, formCategory = category) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(casePayload(next, { category:formCategory, profile:formProfile, reviewed:false })),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Analysis request failed.');
      setAnalysis(data);
      if (!storyTouched) setCaseStory(data.case_file?.narrative?.text || '');
      if (addReply) {
        setMessages([...next, { role: 'assistant', content: data.assistant_message }]);
        const asked = data.case_file?.next_question?.field;
        if (asked) setAskedFields(fields => fields.includes(asked) ? fields : [...fields, asked]);
      }
    } catch (e) { setError(e.message || 'Could not connect to the backend.'); }
    finally { setBusy(false); }
  }

  function toggleVoice() {
    if (listening) { speechRef.current?.stop(); return; }
    if (busy) return;
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setVoiceError('This browser does not support speech recognition. Use typed input or try Chrome.');
      setTranscriptOpen(true);
      return;
    }
    speechRef.current?.cancel();
    setTranscriptDraft('');
    setTranscriptInterim('');
    setSpeechStatus('');
    setVoiceError('');
    setTranscriptOpen(true);
    const controller = createContinuousSpeech({
      Recognition,
      lang: 'en-IN',
      onTranscript: setTranscriptDraft,
      onInterim: setTranscriptInterim,
      onListening: setListening,
      onError: setVoiceError,
      onStatus: setSpeechStatus,
    });
    speechRef.current = controller;
    controller.start();
  }

  function useTranscription() {
    const transcript = transcriptDraft.trim();
    if (!transcript || listening) return;
    const text = [input.trim(), transcript].filter(Boolean).join(' ');
    if (text.length > 2000) {
      setVoiceError('The combined message exceeds 2,000 characters. Please shorten the transcription first.');
      return;
    }
    setInput(text);
    setTranscriptOpen(false);
    setTranscriptDraft('');
    setTranscriptInterim('');
    setVoiceError('');
    textarea.current?.focus();
  }

  function discardTranscription() {
    speechRef.current?.cancel();
    speechRef.current = null;
    setListening(false);
    setSpeechStatus('');
    setTranscriptOpen(false);
    setTranscriptDraft('');
    setTranscriptInterim('');
    setVoiceError('');
  }
  async function practice() {
    if (!sentMessages.length || analysis?.needs_lawyer || argument.trim().length < 10 || practicing) return;
    setPracticing(true); setError(''); setPracticeResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/practice`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages, category, profile, argument }) });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Argument practice failed.');
      setPracticeResult(result);
    } catch (e) { setError(e.message || 'Argument practice failed.'); }
    finally { setPracticing(false); }
  }
  function onSend(event) {
    event?.preventDefault();
    const value = input.trim();
    if (!value || busy) return;
    const next = [...messages, { role: 'user', content: value }];
    setCaseReviewed(false);
    setPlanReviewed(false);
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
    discardTranscription(); setMessages(initialMessages); setArgument(''); setPracticeResult(null); setDocumentType('request');
    setCaseCorrections({}); setCaseTimelineEdits(null); setCaseEvidenceEdits(null);
    setCaseStory(''); setStoryTouched(false); setCaseReviewed(false);
    setAskedFields([]); setResolvedIssues([]); setCaseError('');
    setCompletedActions({}); setPlanReviewed(false); setPlanError('');
    caseId.current = 'CW-' + Math.random().toString(36).slice(2, 11).toUpperCase();
  }
  function openDraftReview() {
    if (!analysis || analysis.needs_lawyer || busy) return;
    const autoFields = analysis.profile_used || {};
    const caseFacts = analysis.case_file?.facts || {};
    const corrected = Object.fromEntries(fieldConfig.map(([key]) => [
      key, profile[key]?.trim() || caseFacts[key]?.value || autoFields[key] || '',
    ]));
    setDraftProfile({ ...emptyProfile, ...autoFields, ...corrected, sender_name: '', sender_contact: '' });
    setDraftFacts(caseStory.trim() || analysis.case_file?.narrative?.text || analysis.summary.draft_facts || '');
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
        body: JSON.stringify({ messages, category, profile: safeProfile, confirmed: true, document_type: documentType }),
      });
      if (!response.ok) {
        const details = await response.json();
        throw new Error(details.detail || 'Could not generate draft.');
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `CaseWise-AI-${documentType}-draft.pdf`;
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
          <div className="category-bar"><span>Type of issue</span><div className="category-controls"><div className="category-select-wrap"><select aria-label="Select civil dispute category" value={category} onChange={e => { const selected = e.target.value; setCategory(selected); markCaseChanged(); setCompletedActions({}); if (sentMessages.length && !busy) callAnalyze(messages, false, profile, selected); }}>{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select><ChevronRight size={14}/></div></div></div>
          <div className="chat-stream" aria-live="polite">
            {messages.map((m,i) => <div className={`chat-message ${m.role}`} key={i}>{m.role === 'assistant' && <div className="chat-avatar"><Scale size={15}/></div>}<div className="chat-content"><div className="chat-speaker">{m.role === 'assistant' ? 'CASEWISE AI' : 'YOU'}</div><p>{m.content}</p></div></div>)}
            {busy && <div className="chat-message assistant"><div className="chat-avatar"><Scale size={15}/></div><div className="chat-content"><div className="chat-speaker">CASEWISE AI</div><p className="loading-text"><LoaderCircle size={14} className="spin"/> Reviewing the facts...</p></div></div>}
            {messages.length === 1 && <div className="samples"><span>Or try an example</span><div className="sample-list">{sampleCases.map(s => <button key={s.label} onClick={() => { setInput(s.text); textarea.current?.focus(); }}>{s.label}<ArrowRight size={13}/></button>)}</div></div>}
            <div ref={bottom}/>
          </div>
          {transcriptOpen && <section className="transcript-review" aria-label="Review voice transcription">
            <div className="transcript-title"><Mic size={16}/><strong>Review voice transcription</strong><span>{listening ? (speechStatus || 'Listening…') : 'Not recording'}</span></div>
            <label htmlFor="casewise-transcription">Speech is transcribed in English. Short pauses are fine; press Stop recording when finished. Then correct any errors before adding the transcription.</label>
            <textarea id="casewise-transcription" rows={3} maxLength={2000} value={transcriptDraft} readOnly={listening} onChange={e => setTranscriptDraft(e.target.value)} placeholder={listening ? 'Speak now — pauses will not submit your recording…' : 'Speech will appear here if recognized.'} />
            {transcriptInterim && <p className="interim-text" aria-live="polite">Hearing: {transcriptInterim}</p>}
            {voiceError && <p className="voice-alert" role="alert">{voiceError}</p>}
            <div className="transcript-actions"><button type="button" onClick={discardTranscription}>Discard</button>{listening && <button type="button" className="recording-stop" onClick={() => speechRef.current?.stop()}><MicOff size={14}/> Stop recording</button>}<button type="button" onClick={useTranscription} disabled={listening || !transcriptDraft.trim()}>Add to message for review</button></div>
          </section>}
          <form className="composer" onSubmit={onSend}><textarea ref={textarea} value={input} rows={2} maxLength={2000} placeholder="Describe what happened, when, and what outcome you want..." onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); } }}/><div className="composer-footer"><span><Info size={13}/> Audio may be processed by your browser's speech provider. Transcript is never sent until you press Send.</span><div className="composer-actions"><button type="button" disabled={busy} aria-label={listening ? 'Stop microphone' : 'Start voice input'} aria-pressed={listening} title={listening ? 'Stop recording and review transcription' : 'Start continuous dictation in English'} onClick={toggleVoice} className={`voice-button ${listening ? 'recording' : ''}`}>{listening ? <MicOff size={16}/> : <Mic size={16}/>}</button><button type="submit" disabled={!input.trim() || busy || listening} className="send-button">Send <Send size={15}/></button></div></div></form>
        </div>
        <div className="footnote"><ShieldAlert size={15}/> CaseWise AI is a demonstration tool, not a lawyer. Check all advice and legal deadlines with a professional.</div>
      </section>
      <aside className={`right-panel ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="right-tabs"><button className={tab === 'summary' ? 'active' : ''} onClick={() => setTab('summary')}><ClipboardList size={16}/> Overview</button><button className={tab === 'timeline' ? 'active' : ''} onClick={() => setTab('timeline')}>Timeline</button><button className={tab === 'evidence' ? 'active' : ''} onClick={() => setTab('evidence')}>Evidence</button><button className={tab === 'review' ? 'active' : ''} onClick={() => setTab('review')}>Review &amp; export</button><button className={tab === 'plan' ? 'active' : ''} onClick={() => setTab('plan')}>Action plan</button><button className={tab === 'details' ? 'active' : ''} onClick={() => setTab('details')}><UserRound size={15}/> Details</button></div>
        <div className="right-content">
          {tab === 'summary' ? <>
            <div className="panel-topline"><span>YOUR CASE FILE</span>{analysis && <span className="category-tag">{analysis.summary.category_label}</span>}</div>
            {!analysis ? <div className="empty-overview"><div className="empty-circle"><BookOpen size={32} strokeWidth={1.6}/></div><h3>Your case starts here</h3><p>Share your situation in the chat. A structured summary, possible next steps, and source links will appear here.</p><button onClick={() => textarea.current?.focus()}>Describe your case <ArrowRight size={14}/></button></div> : <>
              <div className="section-block"><h2>What you've told us</h2><p className="issue-text">{analysis.summary.issue}</p></div>
              {analysis.case_file && <div className="case-brief">
                 <div className="case-meter-top"><strong>Case subtype: {analysis.case_file.subtype.label}</strong><span>{analysis.case_file.completeness.completed}/{analysis.case_file.completeness.total} checks</span></div>
                 <div className="case-meter"><span style={{width:analysis.case_file.completeness.percent+'%'}}/></div>
                 <p>Information collected, not case strength or legal filing readiness.</p>
                 <div className="case-brief-links"><button onClick={()=>setTab('timeline')}>Timeline ({analysis.case_file.timeline.length})</button><button onClick={()=>setTab('evidence')}>Evidence ({analysis.case_file.evidence.length})</button><button onClick={()=>setTab('review')}>Edit &amp; export</button></div>
               </div>}
               <div className="section-block"><h2>Structured case narrative</h2>
                 <p className="issue-text">{analysis.case_file?.narrative?.text || analysis.summary.draft_facts}</p>
                 <p className="source-caveat">Proposed from user statements and/or AI suggestions. Check the dates, evidence and allegations before using it.</p>
                 <h3 className="micro-heading">Where you may stand</h3>
                 <p className="issue-text">{analysis.summary.ai_extracted_case?.position_suggestion || 'Possible options depend on the facts and local rules. Review the official resources below; this is not a legal merits prediction.'}</p>
               </div>
               {Object.keys(analysis.summary.facts_reported).length > 0 && <div className="section-block"><h2>Facts captured</h2><dl className="facts-list">{Object.entries(analysis.summary.facts_reported).map(([k,v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></div>}
              <div className="section-block"><div className="section-header"><h2>Suggested next steps</h2><button className="inline-button" onClick={() => setTab('plan')}>Open action plan <ChevronRight size={13}/></button></div><ol className="steps-list">{analysis.next_steps.map((v,i) => <li key={i}><span className="step-number">{i+1}</span><span>{v}</span></li>)}</ol></div>
              <div className="section-block"><div className="section-header"><h2>Information still needed</h2><button className="inline-button" onClick={() => setTab('details')}>Add details <ChevronRight size={13}/></button></div>{analysis.case_file?.missing?.length ? <div className="missing-tags">{analysis.case_file.missing.map(v => <span key={v.key}>{v.label}</span>)}</div> : <p className="small-success"><CheckCircle2 size={15}/> Case-builder checklist complete. Facts and law still need checking.</p>}</div>
              <div className="section-block"><h2>Official starting points</h2><div className="source-list">{analysis.sources.map(src => <a key={src.id} href={src.url} target="_blank" rel="noopener noreferrer"><span className="source-icon"><Landmark size={16}/></span><span><strong>{src.title}</strong><small>{src.description}</small></span><ExternalLink size={14}/></a>)}</div><p className="source-caveat">{analysis.source_status}</p></div>
              <div className="safety-card"><ShieldAlert size={17}/><div><strong>Know the limits</strong>{analysis.safety_flags.map((flag,i) => <p key={i}>{flag}</p>)}</div></div>
              <div className="draft-card"><div className="draft-icon"><FileDown size={20}/></div><div><strong>Prepare a document</strong><p>Choose a request, notice outline, complaint, reply or application. Review every fact before creating a PDF.</p></div><button disabled={downloading || analysis.needs_lawyer || busy} onClick={openDraftReview}><ClipboardList size={16}/> Review &amp; generate PDF</button></div>
              <div className="practice-card"><h2><MessageSquareText size={16}/> Practise your argument</h2><p>Try explaining your side. CaseWise AI will ask a respectful opposing-side question and suggest improvements. Not a prediction.</p><textarea maxLength={1600} rows={3} value={argument} onChange={e => setArgument(e.target.value)} placeholder="My position is... The evidence is..."/><button onClick={practice} disabled={!sentMessages.length || analysis.needs_lawyer || argument.trim().length < 10 || practicing}>{practicing ? 'Thinking...' : 'Practise with AI'}</button>{practiceResult && <div className="practice-result"><strong>Other side might ask</strong><p>{practiceResult.opponent_question}</p><strong>How to improve your argument</strong><p>{practiceResult.feedback}</p><small>{practiceResult.mode === 'guided-demo' ? 'Offline demo feedback' : 'Gemini-assisted practice; verify details'}</small></div>}</div>
            </>}
          </> : tab === 'plan' ? <LegalPlanPanel plan={analysis?.legal_plan}
    checked={completedActions} onCheck={(id,value) => setCompletedActions(prev => ({...prev,[id]:value}))}
    reviewed={planReviewed} onReviewed={setPlanReviewed}
    onExport={downloadLegalPlan} exporting={planExporting} error={planError}
    onRefresh={refreshLegalPlan} refreshing={busy}
  /> : tab === 'details' ? <div className="details-tab"><div className="panel-topline">OPTIONAL FACT CHECK</div><h2>Complete your case details</h2><p>Add only details you're comfortable sharing. These fields are used to create a clearer summary and draft letter.</p><div className="profile-fields">{fieldConfig.map(([key,label,hint]) => <label key={key}>{label}<input value={profile[key]} maxLength={250} placeholder={hint} onChange={e => {markCaseChanged();setProfile(p => ({ ...p, [key]: e.target.value }));}}/></label>)}</div><button className="update-button" disabled={!sentMessages.length || busy} onClick={async () => { await callAnalyze(messages, false); setTab('summary'); }}>Update case overview <ArrowRight size={16}/></button><p className="privacy-note"><ShieldCheck size={15}/> Case text is not intentionally saved on the server. If Gemini is configured, conversational inputs are sent to its API.</p></div> : <CaseFilePanel mode={tab} file={analysis?.case_file}
    profile={profile} onProfile={(key,value)=>{markCaseChanged();setProfile(p=>({...p,[key]:value}));}}
    corrections={caseCorrections} onCorrection={(key,value)=>{markCaseChanged();setCaseCorrections(p=>({...p,[key]:value}));}}
    timelineEdits={caseTimelineEdits} onTimeline={next=>{markCaseChanged();setCaseTimelineEdits(next);}}
    evidenceEdits={caseEvidenceEdits} onEvidence={next=>{markCaseChanged();setCaseEvidenceEdits(next);}}
    story={caseStory} onStory={next=>{markCaseChanged();setStoryTouched(true);setCaseStory(next);}}
    reviewed={caseReviewed} onReviewed={setCaseReviewed}
    resolvedIssues={resolvedIssues} onResolve={(id,checked)=>{markCaseChanged();setResolvedIssues(prev=>checked?[...new Set([...prev,id])]:prev.filter(x=>x!==id));}}
    onRefresh={saveCaseEdits} onExport={exportCase} exportBusy={caseExportBusy} saving={busy} error={caseError}/>}
          {error && <div className="error-box" role="alert"><ShieldAlert size={16}/> {error}</div>}
        </div>
      </aside>
    </main>
    {reviewOpen && <div className="review-overlay" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget && !downloading) setReviewOpen(false); }}>
      <section className="review-dialog" role="dialog" aria-modal="true" aria-labelledby="review-heading">
        <div className="review-top"><div><span className="panel-topline">BEFORE YOU DOWNLOAD</span><h2 id="review-heading">Review your document draft</h2><p>Information suggested by the chat may be incomplete. Correct any facts below. The draft is a factual request, not a formal legal notice.</p></div><button type="button" className="review-close" aria-label="Close review" onClick={() => setReviewOpen(false)} disabled={downloading}><X size={19}/></button></div>
        <div className="review-body">
          <label className="review-label">Choose document type<select className="doc-type-select" value={documentType} onChange={e=>{setDocumentType(e.target.value);setDraftConfirmed(false)}}>{documentTypes.map(d=><option key={d.value} value={d.value}>{d.label}</option>)}</select><small>All options create a draft for review, never an official filing. Notice and reply drafts need legal review.</small></label>
          <label className="review-label">Your factual account (editable)<textarea rows={5} maxLength={1200} value={draftFacts} onChange={e => { setDraftFacts(e.target.value); setDraftConfirmed(false); }}/><small>PDF drafts are currently in English. Check any AI-suggested narrative, remove questions or unverified claims, and confirm wording before downloading.</small></label>
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
