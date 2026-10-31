/* =====================================================================
   SITE CONTENT: edit this file to update the website.
   No coding needed: change the text between the quotes, save, re-upload.
   - Portraits are background-removed cut-outs (transparent PNG/WebP), with
     no retouching of the face. To swap one, use a transparent image of the
     same kind and keep the same file name, or change the path here.
   - Project `stage` must be one of: "delivered", "ongoing", "concept".
   ===================================================================== */
window.SITE = {
  name: "Dr. Syed Asif Hashmi",
  portraitHero: "assets/cutout-hero.webp",
  portraitCard: "assets/cutout-card.webp",
  portraitStudio: "assets/cutout-studio.webp",
  email: "contact@syedasifhashmi.com", // ← change to your real inbox
  linkedin: "https://www.linkedin.com/in/dr-asifhashmi",
  // WhatsApp number is stored encoded so it never shows on the page.
  // To change it: encode the number (digits only, e.g. 923001234567) at base64encode.org and paste here.
  whatsapp: "OTIzMzMyMTU0NjUx",
  whatsappMessage: "Hello Dr. Asif, I visited syedasifhashmi.com and would like to connect.",

  /* HERO: the big words either side of the portrait.
     Each side has a bright word and a muted word. */
  heroLeft:  ["HEALTH", "CARE"],
  heroRight: ["MEETS", "AI"],
  heroLine:  "Bridging Healthcare, Technology &",
  heroLineItalic: "Innovation",
  heroText:  "Medical doctor and Manager Medical Services at EFU Life Assurance in Karachi, making health insurance decisions faster with data, automation and AI.",

  /* STAT TILES (stair-step grid). Use real numbers only. */
  stats: [
    { value: "8+",   label: "Years in health insurance", lit: true },
    { value: "24/7", label: "Medical approvals, every day" },
    { value: "02",   label: "Awards: 24/7 Center launch & Power BI Best Performer" },
    { value: "05",   label: "Medical officers trained and supervised", lit: true },
    { value: "07",   label: "Web projects built and live" }
  ],

  aboutTitle: "From Clinical Insight to",
  aboutTitleItalic: "Operational Reality",
  about: [
    "Health insurance runs on decisions that are part clinical, part operational and part data. I work where those meet.",
    "I'm a medical doctor (MBBS, 2004) and Manager Medical Services at EFU Life Assurance. My team handles hospital pre-authorization and case management, deciding on clinical necessity, length of stay and policy coverage, and keeps the 24/7 Medical Approval Centre answering around the clock."
  ],
  aboutBold: "Faster answers for patients and hospitals, with doctors still accountable for clinical decisions.",
  aboutAfter: "Alongside the job I make the process measurable: daily case-trend reports, turnaround-time dashboards by time band and region, a system gap analysis to automate the pre-authorization form, and AI integration with the health services app team. I also build small web tools to test ideas; seven of them are live below.",

  /* LEARNING cards. Fill in your degree and institution. */
  learning: [
    { title: "Bachelor of Medicine, Bachelor of Surgery (MBBS)", sub: "Jinnah Medical & Dental College · 1998–2004", text: "The clinical foundation behind every approval: reading a case the way the treating doctor does." },
    { title: "Diploma in Digital Innovation & AI Strategy", sub: "IoBM · 2026 · in progress", text: "Strategy, business cases and responsible adoption of AI, applied to health insurance operations.", featured: true },
    { title: "Data Analytics Mastery with Power BI", sub: "IoBM CIT · 2024 · Best Performer", text: "Power BI for turning operational data into dashboards and decisions, now applied to medical case and turnaround-time reporting." }
  ],

  /* AREAS OF EXPERTISE around the ring */
  expertise: [
    { title: "Clinical Review", text: "Medical justification for admission, length of stay and treatment, decided within policy terms." },
    { title: "Health Insurance", text: "Pre-authorization, claims and case management for hospitals and members, day and night." },
    { title: "Data & Analytics", text: "ERP extracts cleaned into daily case trends, TAT bands and dashboards the team acts on." },
    { title: "AI & Automation", text: "Automating the pre-authorization form and shaping safe AI use cases for medical operations." }
  ],

  projects: [
    {
      id: "mac", stage: "delivered", visual: "clock", tag: "Medical operations",
      title: "24/7 Medical Approval Centre",
      overview: "Round-the-clock medical approvals so hospitals get a decision whenever a patient arrives.",
      bullets: ["Approvals answered 24 hours a day", "Doctor duty hours matched to call volume", "Launch award from EFU Life's MD & CEO, Oct 2025"],
      problem: "Hospitals admit patients at all hours, but approvals depended on office-hour availability.",
      solution: "A staffed approval centre with doctor duty hours mapped to call volume across the day.",
      role: "Contributed to developing the centre; plans doctor coverage against monthly call volumes.",
      methods: ["Duty-hour rostering", "Call-volume analysis", "Policy-based case review"],
      impact: "Recognised with an award for the successful launch of the 24/7 Approval Center (Oct 2025), received from EFU Life's MD & CEO, and named Performer of the Quarter for establishing the Medical Approval Centre."
    },
    {
      id: "pa", stage: "ongoing", visual: "flow", tag: "Workflow automation",
      title: "Pre-Authorization Automation",
      overview: "Fewer manual steps between a hospital's request and an approval decision.",
      bullets: ["Automated pre-authorization form", "Less re-keying between systems", "Faster turnaround per case"],
      problem: "Manual form handling slows processing and invites data-entry errors.",
      solution: "Automate the Pre-Authorization Form and streamline the approval workflow.",
      role: "Leads the requirements from the Medical Services side.",
      methods: ["Workflow mapping", "Gap analysis", "Form automation"],
      impact: "Target: faster turnaround and fewer human errors on every case."
    },
    {
      id: "bi", stage: "ongoing", visual: "bars", tag: "Analytics",
      title: "Medical Services BI Dashboard",
      overview: "Dashboards for medical cases, approval trends and turnaround time.",
      bullets: ["TAT bands from 15 minutes to 24 hours+", "Conventional vs takaful views", "Clean, de-duplicated ERP data"],
      problem: "Raw ERP extracts arrive messy: blank rows, misaligned data, duplicate IDs, mixed date formats.",
      solution: "Cleaning rules plus TAT bands (15 min, 30 min, 60 min, 24 h+) with conventional vs takaful views.",
      role: "Defines the metrics, cleaning rules and the questions the dashboard must answer.",
      methods: ["Excel", "TAT banding", "Trend & outlier analysis"],
      impact: "Daily visibility on where cases slow down and why."
    },
    {
      id: "erp", stage: "ongoing", visual: "nodes", tag: "Systems",
      title: "ERP & Centegy Optimization",
      overview: "A gap analysis of two core systems to choose the faster, less error-prone path.",
      bullets: ["Side-by-side process comparison", "Integration gaps identified", "Standardised workflow"],
      problem: "Two systems, overlapping steps and re-keying between them.",
      solution: "A structured gap analysis to standardise the process and close integration gaps.",
      role: "Owns the medical-operations view of the comparison.",
      methods: ["Gap analysis", "Process standardisation", "System integration"],
      impact: "A clear basis for integration decisions and the PA form automation."
    },
    {
      id: "digital", stage: "delivered", visual: "phone", tag: "Digital health",
      title: "Health Services App",
      overview: "Technology-enabled access to care through the health services app.",
      bullets: ["Consultants added to mHealth teleconsultation", "Grew the network of hospitals", "Discount Centre support"],
      problem: "Members need quick access to doctors, hospitals and discounts.",
      solution: "Adding consultants to mHealth teleconsultation, network hospitals and Discount Centre support.",
      role: "Member of the health services app team; medical content and network inputs.",
      methods: ["Teleconsultation", "Provider network", "App operations"],
      impact: "Broader in-app access to consultations and network hospitals."
    },
    {
      id: "ai", stage: "concept", visual: "spark", tag: "Artificial intelligence",
      title: "AI for Claims & Approvals",
      overview: "Practical, reviewable AI use cases for claims and pre-authorization.",
      bullets: ["Intelligent document processing", "Decision support for reviewers", "Claims automation roadmap"],
      problem: "Reviewers spend time reading documents and re-entering data instead of deciding.",
      solution: "Claims automation, intelligent document processing, analytics and decision-support workflows.",
      role: "Shapes use cases as part of AI integration work and the IoBM AI Strategy diploma.",
      methods: ["Generative AI", "Document processing", "Decision support"],
      impact: "A roadmap for safe, reviewable AI inside medical operations."
    }
  ],

  journeyTitle: "Eight Years at the",
  journeyTitleItalic: "Approval Desk",
  journeyText: "A career built one hospital case at a time, from reviewing pre-authorizations to leading Medical Services.",
  journeyNumber: "8+",
  timeline: [
    { role: "Manager, Medical Services", when: "May 2024 – Present", org: "EFU Life Assurance Ltd. · Karachi",
      text: "Oversees medical pre-authorization operations and the approval and case management teams. Contributed to establishing the 24/7 Medical Approval Center, and works with technology teams on workflows, dashboards and turnaround time. Key initiatives: pre-authorization process improvement, healthcare systems development, operational dashboards and digital healthcare services." },
    { role: "Deputy Manager, Medical Services", when: "Jan 2022 – May 2024", org: "Allianz EFU Health Insurance Ltd. · Karachi",
      text: "Shared responsibility for hospital pre-authorization decisions and daily medical operations. Supervised and trained 5 medical officers and grew the network of hospitals." },
    { role: "Assistant Manager, Medical Services", when: "Dec 2018 – Jan 2022", org: "Allianz EFU Health Insurance Ltd.",
      text: "Reviewed hospital pre-authorization and medical claims against clinical justification and policy terms, and handled hospital and client queries on approvals." }
  ],

  milestones: [
    { when: "Oct 2026", text: "Named Performer of the Quarter for the Medical Approval Centre team's work" },
    { when: "Sep 2026", text: "Started IoBM's Diploma in Digital Innovation and AI Strategy" },
    { when: "Jul 2026", text: "Interviewer and observer for EFU Life's QUEST 2026 Management Trainee Program" },
    { when: "Oct 2025", text: "Award for the successful launch of the 24/7 Approval Center, from EFU Life's MD & CEO" },
    { when: "Dec 2024", text: "Best Performer, Data Analytics Mastery with Power BI, IoBM CIT" },
    { when: "May 2024", text: "Promoted to Manager, Medical Services at EFU Life" }
  ],

  /* LIVE WORK: sites you have published. Each card links to the live site.
     `img` is a screenshot in assets/work/. `wide: true` makes a card span two columns. */
  work: [
    { title: "EFU Medical Services CMIS", kind: "Case management system · Beta", url: "https://cmis.syedasifhashmi.com/", img: "assets/work/cmis.webp", wide: true,
      text: "A case management system for medical services: case intake, daily follow-ups, hospitals and CSOs, region-based access for doctors and managers, and a dashboard for TAT compliance. Runs on invented demo patient data.",
      tags: ["Case management", "Dashboards", "Role-based access"] },
    { title: "BijliSmart", kind: "Electricity bill estimator", url: "https://bijlismart.syedasifhashmi.com/", img: "assets/work/bijlismart.webp",
      text: "Estimate electricity use and bills in Pakistan from your appliances or meter readings, see how tariff slabs change the bill, and plan savings, in English or Urdu.",
      tags: ["Calculator", "English & Urdu"] },
    { title: "Raftaar", kind: "Internet speed test", url: "https://raftar.syedasifhashmi.com/", img: "assets/work/raftaar.webp",
      text: "Measure ping, jitter, download and upload speed in about 25 seconds, right in the browser, with a history of past tests. No app needed.",
      tags: ["Web app", "Networking"] },
    { title: "ICD-10 Code Finder", kind: "Medical coding tool", url: "https://icd10.syedasifhashmi.com/", img: "assets/work/icd10.webp",
      text: "Search 74,879 billable FY2027 ICD-10-CM diagnosis codes and ICD-10-PCS procedure codes by code or keyword, built from the official CMS code files. Tap a code to copy it.",
      tags: ["ICD-10-CM", "ICD-10-PCS", "Medical coding"] },
    { title: "Taleem Dost", kind: "University admissions guide", url: "https://taleemdost.syedasifhashmi.com/", img: "assets/work/taleemdost.webp",
      text: "Shows which Pakistani university programs your SSC and HSSC marks qualify for, with links to official requirements and scholarships. Free, no sign-up.",
      tags: ["Education", "Pakistan"] },
    { title: "Care Nearby", kind: "Healthcare navigation", url: "https://carenearby.lovable.app/", img: "assets/work/carenearby.webp",
      text: "Find nearby hospitals, pharmacies and clinics with directions, phone numbers and opening hours, using your location only to search. Free sign-in.",
      tags: ["Geolocation", "Maps"] },
    { title: "PET Solutions", kind: "Business website", url: "https://petsolutions.syedasifhashmi.com/", img: "assets/work/petsolutions.webp",
      text: "A website for a PET preform and bottle manufacturer: product range, applications, FAQs and a product enquiry flow.",
      tags: ["Business site", "Enquiries"] }
  ],

  skills: ["Healthcare management", "Health insurance", "Digital transformation", "Data analytics", "AI implementation", "Power BI", "Web development", "Team building", "Medical case management", "On-call facilitation of insured members", "Medical facilities", "Pre-authorization", "Medical claims", "ICD-10 coding", "Policy interpretation", "Turnaround-time analysis", "Excel", "BI dashboards", "Process automation", "Generative AI", "Team leadership", "Stakeholder coordination"]
};
