"""Conservative, curated India-wide navigation sources, reviewed 2026-11-08.

These links are *not* a representation that a user's claim satisfies a legal test.
State-specific laws, limitation and eligibility are deliberately not guessed.
"""

VERIFIED_ON = "2026-11-08"

SOURCES = {
    "nalsa": {
        "id": "nalsa",
        "title": "National Legal Services Authority — Legal Aid",
        "url": "https://nalsa.gov.in/legal-aid/",
        "description": "Official guidance on applying for legal aid through legal services authorities; eligibility must be checked.",
    },
    "nch": {
        "id": "nch",
        "title": "National Consumer Helpline",
        "url": "https://consumerhelpline.gov.in/public/contact",
        "description": "Government consumer grievance help; available channels include the NCH portal and helpline 1915.",
    },
    "ejagriti": {
        "id": "ejagriti",
        "title": "e-Jagriti — Consumer Commissions",
        "url": "https://e-jagriti.gov.in/",
        "description": "Official consumer-commission platform for complaint filing and case tracking; jurisdiction and admissibility require checking.",
    },
    "samadhan": {
        "id": "samadhan",
        "title": "Chief Labour Commissioner — Online Services",
        "url": "https://clc.gov.in/clc/online-services",
        "description": "Official information on SAMADHAN for eligible industrial disputes and worker claims; coverage depends on worker status and applicable law.",
    },
    "contract": {
        "id": "contract",
        "title": "India Code — Indian Contract Act, 1872",
        "url": "https://www.indiacode.nic.in/handle/123456789/2187?col=123456789%2F1362",
        "description": "Official central statute reference. Whether and how it applies depends on the agreement and facts.",
    },
}

CATEGORIES = {
    "property": {
        "title": "Property & rental",
        "terms": ["landlord", "tenant", "rent", "rental", "security deposit", "evict", "lease", "house", "flat", "property", "possession", "apartment"],
        "questions": [
            "What state is the property in, and do you have a written rental or sale agreement?",
            "What amount or property is disputed, and what reason has the other person given?",
            "Do you have receipts, messages, a signed agreement, or photos that support your account?",
        ],
        "steps": [
            "Save the agreement, payment records, notices and relevant messages in date order.",
            "Write a factual request for clarification or resolution to the other party and keep proof of delivery.",
            "Ask a local civil lawyer or legal-aid office to check the applicable state rules and any filing deadline.",
        ],
        "source_ids": ["nalsa", "contract"],
    },
    "consumer": {
        "title": "Consumer complaint & refund",
        "terms": ["refund", "consumer", "product", "seller", "delivery", "purchase", "shopping", "defective", "merchant", "service provider", "warranty", "return order", "online order"],
        "questions": [
            "When did you pay or place the order, and what did the seller promise?",
            "Have you already contacted the seller, and what response did they give?",
            "Do you have the invoice, order confirmation, payment receipt and complaint messages?",
        ],
        "steps": [
            "Collect the invoice, order ID, payment proof and messages with the business.",
            "Send a clear written request for the refund, repair or other resolution you seek.",
            "Consider the National Consumer Helpline; check eligibility and procedure before any Consumer Commission filing on e-Jagriti.",
        ],
        "source_ids": ["nch", "ejagriti", "nalsa"],
    },
    "employment": {
        "title": "Employment & unpaid salary",
        "terms": ["salary", "wages", "employer", "employee", "job", "payroll", "paycheck", "overtime", "termination", "office", "company", "unpaid pay", "pending payment from employer"],
        "questions": [
            "What is your role, state of employment, and type of employment agreement?",
            "For which pay periods is money unpaid, and have you asked the employer in writing?",
            "Do you have payslips, attendance records, an offer letter or emails?",
        ],
        "steps": [
            "Preserve your offer letter or contract, payslips, bank records, and written requests to the employer.",
            "Ask the employer or HR in writing for the payment breakdown and a proposed resolution.",
            "Check whether a relevant labour authority or SAMADHAN process applies to your status and claim; seek professional advice on deadlines.",
        ],
        "source_ids": ["samadhan", "nalsa"],
    },
    "contract": {
        "title": "Contract & payment",
        "terms": ["contract", "agreement", "invoice", "borrow", "loan", "debt", "client", "vendor", "service fee", "freelance", "breach", "payment due", "unpaid invoice"],
        "questions": [
            "What did the parties agree to, and is it recorded in writing?",
            "Which payment or obligation is overdue, and when was it due?",
            "What messages, invoices, receipts or witnesses support your description?",
        ],
        "steps": [
            "Collect the contract, invoices, proof of performance and payment records.",
            "Request the outstanding payment or agreed performance in writing, without asserting unverified legal penalties.",
            "Have a lawyer check whether the agreement, limitation rules and dispute-resolution terms affect your options.",
        ],
        "source_ids": ["contract", "nalsa"],
    },
    "other": {
        "title": "Needs category review",
        "terms": [],
        "questions": [
            "Is your issue about property/rent, a consumer purchase, employment pay, or a contract?",
            "Which state is this in, what happened, and when?",
            "What written evidence, notices or deadlines do you have?",
        ],
        "steps": [
            "Preserve a dated account of events and relevant documents.",
            "Identify the state and the type of dispute before selecting a legal route.",
            "Ask an appropriate legal-aid office or qualified lawyer about next steps.",
        ],
        "source_ids": ["nalsa"],
    },
}

ALLOWED_CATEGORIES = tuple(CATEGORIES)
