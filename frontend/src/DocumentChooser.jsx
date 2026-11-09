import React from 'react';
import { FileCheck2, FileText, Mail, MessageSquareReply, ScrollText } from 'lucide-react';

export const documentTypes = [
  { value: 'request', label: 'Resolution request', description: 'Ask the other party to resolve the dispute.', icon: Mail },
  { value: 'notice', label: 'Legal notice outline', description: 'Prepare a proposed notice for qualified lawyer review.', icon: ScrollText },
  { value: 'complaint', label: 'Complaint draft', description: 'Describe a grievance for an appropriate office or organization.', icon: FileText },
  { value: 'reply', label: 'Reply draft', description: 'Respond to a communication or allegation with lawyer review.', icon: MessageSquareReply },
  { value: 'application', label: 'Application for assistance', description: 'Request help from a relevant institution, subject to eligibility.', icon: FileCheck2 },
];

export default function DocumentChooser({ onChoose, disabled = false }) {
  return <section className="document-chooser" aria-label="Choose what document to prepare">
    <div className="document-chooser-heading">
      <h2>What would you like to prepare?</h2>
      <p>Select the draft you need. You can review and correct all the facts before creating a PDF.</p>
    </div>
    <div className="document-choice-grid">
      {documentTypes.map(({value, label, description, icon: Icon}) => (
        <button key={value} type="button" disabled={disabled} onClick={() => onChoose(value)}
          className="document-choice">
          <Icon size={18} aria-hidden="true"/>
          <span><strong>{label}</strong><small>{description}</small></span>
        </button>
      ))}
    </div>
    <p className="document-choice-caution">These are informational drafts, not official filings. A notice, reply, or formal complaint may need legal review and forum-specific procedures.</p>
  </section>;
}
