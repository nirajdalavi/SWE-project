# Aqeed.ai User Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Workspace Management](#workspace-management)
3. [Modes and Features](#modes-and-features)
   - [Vendor Recommendation Mode](#1-vendor-recommendation-mode)
   - [Vendor Comparison Mode](#2-vendor-comparison-mode)
   - [Vendor Research Mode](#3-vendor-research-mode)
   - [Ask Question Mode](#4-ask-question-mode)
   - [Score Contracts Mode](#5-score-contracts-mode)
   - [Combined Evaluation Mode](#6-combined-evaluation-mode)
   - [Resume Scoring Mode](#7-resume-scoring-mode)
   - [Audit Mode](#8-audit-mode)
   - [Legal Analysis Mode](#9-legal-analysis-mode)
4. [Additional Features](#additional-features)

---

## Getting Started

Aqeed.ai is an AI-powered procurement and contract analysis platform that helps you make better vendor decisions, analyze contracts, score resumes, and more.

### First Time Setup
1. Access the application at your deployment URL or `http://localhost:3000` for local development or `https://aqeed-aws.cloud` or `https://aqeed-gcp.cloud`.
2. Create a workspace to organize your projects
3. Select a mode based on your needs

---

## Workspace Management

### Creating a Workspace
1. Click the **"Create Workspace"** button in the header
2. Enter a unique workspace name (lowercase, no spaces)
3. Click **"Create"** to confirm

### Selecting a Workspace
- Use the workspace dropdown in the header to switch between workspaces
- Each workspace maintains its own documents, criteria, and results

### Deleting a Workspace
1. Select the workspace you want to delete
2. Click the **"Delete Workspace"** button
3. Confirm the deletion

---

## Modes and Features

### 1. Vendor Recommendation Mode

**Purpose**: Get AI-powered vendor recommendations based on your project requirements.

#### How to Use:
1. **Select Mode**: Click **"Find Vendors"** from the welcome screen
2. **Fill in Project Details**:
   - **Project Requirements**: Describe what you need (e.g., "cloud hosting provider with 99.9% uptime")
   - **Industry**: Select your industry (general, technology, construction, healthcare, etc.)
   - **Location Preference**: Choose preferred vendor location (any, local, national, international)
   - **Number of Vendors**: Select how many recommendations you want (3-10)
   - **Preference**: Choose your priority (cost-effective, quality-focused, or balanced)
   - **Vendor Type**: Auto-detect or specify (service providers, technology vendors, equipment suppliers)

3. **Enable Optional Analysis** (checkboxes):
   - **Reddit Analysis**: Analyze community discussions about vendors
   - **Google Reviews**: Include customer review analysis
 

4. **Submit**: Click **"Get Recommendations"**

#### Results Include:
- Vendor name and location
- Overall score and ranking
- Detailed analysis of strengths and weaknesses
- Contact information
- Pricing estimates
- Social proof (if enabled)
- Reddit discussions (if enabled)

#### Actions Available:
- **Download PDF**: Export recommendations as a professional report
- **Email Report**: Send recommendations to stakeholders
- **Express Interest**: Send automated inquiry emails to vendors
- **View Details**: Expand vendor cards for full analysis

---

### 2. Vendor Comparison Mode

**Purpose**: Compare multiple vendors side-by-side across various criteria.

#### How to Use:
1. **Select Mode**: Click **"Compare Vendors"** from the welcome screen
2. **Add Vendors**:
   - Enter vendor name and location
   - Click **"+"** to add more vendors (minimum 2)
   - Click **"-"** to remove vendors
3. **Submit**: Click **"Compare Vendors"**

#### Results Include:
- Side-by-side comparison table
- Scores across multiple criteria:
  - Technical capabilities
  - Pricing and value
  - Customer service
  - Reliability and reputation
  - Innovation and technology
  - Scalability
  - Support and maintenance
- Overall rankings
- Winner determination with rationale

#### Best Practices:
- Add 2-5 vendors for optimal comparison
- Include location for more accurate results
- Use after getting initial recommendations

---

### 3. Vendor Research Mode

**Purpose**: Deep-dive research into a specific vendor.

#### How to Use:
1. **Select Mode**: Click **"Research Vendor"** from the welcome screen
2. **Enter Vendor Details**:
   - **Vendor Name**: Full company name
   - **Location**: City, state, or country
3. **Enable Optional Analysis**:
   - Reddit Analysis
   - Google Reviews
4. **Submit**: Click **"Research Vendor"**

#### Results Include:
- Company overview and background
- Strengths and weaknesses
- Market position
- Customer sentiment analysis
- Social media presence
- Professional network analysis
- Review summaries

#### Use Cases:
- Due diligence before vendor selection
- Competitive analysis
- Market research
- Risk assessment

---

### 4. Ask Question Mode

**Purpose**: Ask questions about your uploaded documents and get AI-powered answers with citations.

#### How to Use:
1. **Select Mode**: Click **"Ask Questions"** from the welcome screen
2. **Upload Documents**:
   - Click **"Upload Documents"** tab
   - Select PDF, Word, or text files
   - Click **"Upload"** to process
3. **Ask Questions**:
   - Type your question in the text area
   - Enable **"Compare with ChatGPT"** for dual AI responses (optional)
   - Enable **"Share data with ChatGPT"** to include document context (optional)
   - Enable **"Use Web Search"** for internet-augmented answers (optional)
   - Select **Response Size**: short, medium, or long
   - Select **Response Type**: sentence, paragraph, or detailed
4. **Submit**: Click **"Ask Question"**

#### Results Include:
- AI-generated answer
- Source citations with page numbers
- Comparison with ChatGPT (if enabled)
- Response time metrics
- PDF viewer with highlighted sources

#### Advanced Features:
- **Language Translation**: Translate answers to 50+ languages
- **Web Search**: Augment answers with real-time web data
- **Specific URL**: Focus search on a particular website
- **Citation Viewer**: Click sources to view exact document locations

#### Best Practices:
- Upload relevant documents before asking questions
- Be specific in your questions
- Use web search for current information
- Compare responses for critical decisions

---

### 5. Score Contracts Mode

**Purpose**: Evaluate and score multiple contracts or proposals against custom criteria.

#### How to Use:
1. **Select Mode**: Click **"Score Contracts"** from the welcome screen
2. **Upload Documents**:
   - Upload contract PDFs or proposals
   - Upload criteria document 
3. **Define Criteria**:
   - Enter evaluation criteria in the text area
   - Set maximum score (default: 5)
   - Example: "Evaluate based on pricing, delivery time, quality guarantees, and support"
4. **Configure Options**:
   - Enable **"Compare with ChatGPT"** for dual scoring
   - Enable **"Share data with ChatGPT"** for context
5. **Submit**: Click **"Score Contracts"**

#### Results Include:
- **Scoring Matrix**: Detailed scores for each contract per criterion
- **Final Scores Table**: Overall rankings
- **Best Proposal Summary**: Winner with justification
- **Detailed Rationale**: Explanation for each score

#### Actions Available:
- **Export Report**: Download as PDF or Excel
- **Submit to Admin**: Send for approval
- **View Comparison**: See side-by-side analysis
- **Translate**: Convert results to other languages

#### Use Cases:
- RFP evaluation
- Proposal comparison
- Vendor selection
- Contract analysis

---

### 6. Combined Evaluation Mode

**Purpose**: Combine technical and financial scores with custom weighting for holistic evaluation.

#### How to Use:
1. **Select Mode**: Click **"Combined Evaluation"** from the welcome screen
2. **Upload Documents**:
   - Upload technical proposals
   - Upload financial proposals
3. **Set Weights**:
   - Adjust **Technical Weight** slider (0-100%)
   - Adjust **Financial Weight** slider (0-100%)
   - Weights must sum to 100%
4. **Submit**: Click **"Evaluate"**

#### Results Include:
- Combined scores with weighted calculation
- Technical scores breakdown
- Financial scores breakdown
- Overall rankings
- Best proposal recommendation

#### Use Cases:
- Complex procurement decisions
- Multi-criteria evaluation
- Balanced vendor selection
- Budget-constrained projects

---

### 7. Resume Scoring Mode

**Purpose**: Automatically score and rank resumes against job requirements.

#### How to Use:
1. **Select Mode**: Click **"Score Resumes"** from the welcome screen
2. **Upload Files**:
   - **Resumes Tab**: Upload candidate resumes (PDF format)
   - **Job Description Tab**: Upload job description
3. **Extract Criteria**:
   - Click **"Extract Criteria"** to auto-generate evaluation criteria from JD
   - Review and edit criteria as needed
   - Add/remove criteria
   - Adjust weights for each criterion
4. **Score Resumes**:
   - Click **"Score Resumes"**
   - Wait for AI analysis

#### Results Include:
- **Resume Rankings**: Sorted by overall score
- **Detailed Scores**: Per-criterion breakdown
- **Rationale**: Explanation for each score
- **Citations**: Specific resume sections supporting scores
- **Top Candidates**: Highlighted best matches

#### Actions Available:
- **Sort**: Ascending or descending by score
- **Edit Scores**: Manually adjust if needed
- **Save Changes**: Persist manual edits
- **Email Results**: Send to hiring manager
- **Export**: Download as Excel
- **View Citations**: See exact resume excerpts

#### Best Practices:
- Upload clear, well-formatted resumes
- Review auto-extracted criteria
- Adjust criterion weights based on priority
- Use citations to verify scores
- Select top 3-5 candidates for interviews

---

### 8. Audit Mode

**Purpose**: Perform comprehensive contract audits to identify risks, compliance issues, and optimization opportunities.

#### How to Use:
1. **Select Mode**: Click **"Audit Contracts"** from the welcome screen
2. **Upload Contracts**:
   - Upload contract documents (PDF, Word)
   - Multiple contracts can be analyzed together
3. **Run Audit**: Click **"Run Contract Audit"**

#### Results Include:
- **Executive Summary**: High-level findings
- **Risk Assessment**: Identified risks with severity levels
- **Compliance Analysis**: Regulatory and legal compliance check
- **Financial Review**: Cost analysis and optimization opportunities
- **Recommendations**: Actionable improvement suggestions
- **Detailed Findings**: Section-by-section analysis

#### Report Sections:
- Contract Overview
- Key Terms and Conditions
- Risk Factors
- Compliance Status
- Financial Implications
- Recommendations
- Action Items

#### Actions Available:
- **Expand/Collapse Sections**: Navigate report easily
- **Edit Report**: Customize findings
- **Download PDF**: Export audit report
- **Save Changes**: Persist edits

#### Use Cases:
- Pre-signature contract review
- Periodic contract audits
- Risk management
- Compliance verification
- Contract optimization

---

### 9. Legal Analysis Mode

**Purpose**: Conduct legal analysis of contracts to identify legal issues, obligations, and risks.

#### How to Use:
1. **Select Mode**: Click **"Legal Analysis"** from the welcome screen
2. **Upload Contracts**: Upload legal documents
3. **Run Analysis**: Click **"Run Legal Analysis"**

#### Results Include:
- **Legal Summary**: Overview of legal position
- **Obligations Analysis**: Party responsibilities
- **Rights and Remedies**: Legal protections
- **Liability Assessment**: Exposure and limitations
- **Termination Clauses**: Exit conditions
- **Dispute Resolution**: Arbitration and jurisdiction
- **Compliance Requirements**: Legal obligations
- **Risk Factors**: Legal risks identified

#### Report Sections:
- Legal Framework
- Contractual Obligations
- Rights and Remedies
- Liability and Indemnification
- Termination and Renewal
- Dispute Resolution
- Compliance and Regulatory
- Legal Recommendations

#### Actions Available:
- **Navigate Sections**: Expand/collapse for easy reading
- **Edit Analysis**: Add legal notes
- **Download Report**: Export as PDF
- **Save Changes**: Persist modifications

#### Use Cases:
- Contract legal review
- Pre-negotiation analysis
- Legal risk assessment
- Compliance verification
- Due diligence

---

## Additional Features

### Prompt Manager
- **Access**: Click **"Manage Prompts"** in the header
- **Purpose**: View and manage AI prompts used by the system
- **Features**: 
  - View prompts by category
  - Understand how AI processes requests
  - System transparency

### Metrics Dashboard
- **Access**: Click **"View Metrics"** in the header
- **Purpose**: Track system usage and performance
- **Metrics Shown**:
  - Response times by mode
  - Usage patterns
  - Performance trends
  - Historical data

### Theme Toggle
- **Access**: Click the theme icon in the header
- **Options**: Light mode / Dark mode
- **Persistence**: Preference saved automatically

### Contact Form
- **Access**: Click **"Contact Us"** in the header
- **Purpose**: Submit feedback, questions, or feature requests
- **Fields**: Name, email, subject, message

### Feature Request
- **Access**: Click **"Request Feature"** from welcome screen
- **Purpose**: Suggest new features or improvements
- **Process**: Submit ideas directly to development team

---

## Tips for Best Results

### Document Upload
- Use clear, well-formatted PDFs
- Ensure text is selectable (not scanned images)
- Upload relevant documents only
- Organize by workspace for better management

### Question Formulation
- Be specific and clear
- Ask one question at a time
- Provide context when needed
- Use web search for current information

### Criteria Definition
- Be explicit about what matters
- Use measurable criteria when possible
- Prioritize criteria by importance
- Review auto-extracted criteria before scoring

### Workspace Organization
- Create separate workspaces for different projects
- Use descriptive workspace names
- Delete old workspaces to stay organized
- Keep related documents in the same workspace

### Performance Optimization
- Large documents may take longer to process
- Enable ChatGPT comparison only when needed
- Use async mode for long-running tasks
- Wait for processing to complete before new requests





