import React from 'react';

const specificFields = {
  request: [
    {name:'prior_contact', label:'Earlier attempts to resolve this (optional)', hint:'e.g. I requested a refund twice by email'},
  ],
  notice: [
    {name:'prior_contact', label:'Earlier communications (optional)', hint:'e.g. I sent a request on a specific date and received no answer'},
  ],
  complaint: [
    {name:'prior_contact', label:'Earlier steps or complaints (optional)', hint:'e.g. Contacted the business; include the reply if you have it'},
    {name:'office_action', label:'What should the office consider doing? (optional)', hint:'e.g. Review my grievance and explain available complaint procedures'},
  ],
  reply: [
    {name:'received_communication', label:'What notice, claim or message are you replying to?', hint:'Describe the actual communication received, its sender and date if known', highlight:true},
    {name:'reply_points', label:'Which specific allegations or points do you want to answer?', hint:'Enter the points from the actual communication; do not guess them'},
  ],
  application: [
    {name:'assistance_requested', label:'What kind of assistance are you seeking?', hint:'e.g. Information about eligibility for legal aid or mediation'},
    {name:'prior_contact', label:'Earlier steps, if any (optional)', hint:'e.g. I spoke to the landlord and asked for a written response'},
  ],
};

export default function DocumentExtraFields({type, values, onChange}) {
  const fields = specificFields[type] || [];
  if (!fields.length) return null;
  return <section className="document-specific-fields">
    <h3>Details for this {type} draft</h3>
    <p>These fields make the generated document specific to your purpose. Leave unknown information blank; the draft will show a review placeholder instead of inventing facts.</p>
    {fields.map(field => <label className="review-label" key={field.name}>
      {field.label}{field.highlight && <span className="field-required"> Important for a meaningful reply</span>}
      <textarea rows={field.highlight ? 3 : 2} maxLength={700} value={values[field.name] || ''}
        placeholder={field.hint} onChange={event=>onChange(field.name,event.target.value)}/>
    </label>)}
    {type==='reply' && !values.received_communication?.trim() && <p className="document-specific-warning">
      No incoming notice or complaint has been described. CaseWise AI can generate only a reply outline with placeholders, not a complete factual response.
    </p>}
    {(type==='complaint'||type==='application') && !values.recipient_name?.trim() && <p className="document-specific-warning">
      The recipient is still unspecified. Confirm the correct office and its procedure before using this draft.
    </p>}
  </section>;
}
