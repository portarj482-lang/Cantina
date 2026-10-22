# AI Bug Bounty Research Playbook

## Purpose and authorization boundary

This is a living research and learning system for finding high-impact vulnerabilities in AI-enabled applications through authorized bug bounty programs, labs, and systems you own. Always follow the exact program scope, safe-harbor terms, rate limits, data-handling restrictions, and disclosure rules. Stop testing if there is a risk of harming users, accessing unnecessary personal data, disrupting service, or crossing an out-of-scope boundary.

---

## 1. The key idea: AI bug bounty is two security disciplines joined together

An AI product normally contains a conventional application stack plus AI-specific components. High-value findings often occur at the seam between them.

### Conventional application surface

- Identity, authentication, sessions, OAuth, API keys, and tokens
- Authorization and tenant isolation
- Web, mobile, desktop, browser extension, and API clients
- Backend APIs, GraphQL, WebSockets, queues, and background jobs
- Cloud storage, databases, caches, logs, analytics, and admin systems
- Billing, quotas, subscriptions, invitations, exports, and support tools
- CI/CD, containers, dependencies, secrets, and infrastructure

### AI-specific surface

- System and developer instructions
- Prompt templates and conversation state
- Retrieval-augmented generation, vector stores, embeddings, document ingestion, and citations
- Agents, tools, plugins, connectors, function calling, and Model Context Protocol servers
- Model gateways, inference APIs, guardrails, classifiers, and moderation
- Fine-tuning, training data, evaluation data, feedback data, and model registries
- Model files, tokenizers, adapters, checkpoints, and serialization formats
- Multimodal inputs and outputs
- Memory, long-running tasks, autonomous workflows, and human approval gates

The OWASP 2025 LLM risk set includes prompt injection, sensitive information disclosure, supply-chain risk, data and model poisoning, improper output handling, excessive agency, system prompt leakage, vector and embedding weaknesses, misinformation, and unbounded consumption.

---

## 2. Priority vulnerability family: access-control bypass

Access control decides whether an authenticated or unauthenticated actor may perform an action or access a resource. It depends on authentication and session management but is a separate enforcement layer. PortSwigger divides it into vertical, horizontal, and context-dependent controls.

### 2.1 Missing ownership checks

Test whether the server verifies that the current actor owns, belongs to, or is explicitly permitted to use the target object.

AI-relevant objects include:

- Conversations, messages, assistants, agents, prompts, memories, and shared links
- Uploaded documents, generated files, images, audio, transcripts, and exports
- Vector indexes, collections, chunks, embeddings, and retrieval sources
- Fine-tunes, datasets, evaluations, runs, traces, logs, feedback, and model artifacts
- API keys, connectors, credentials, tool configurations, webhooks, and MCP servers
- Workspaces, projects, organizations, tenants, teams, invitations, and billing objects
- Jobs, queues, scheduled tasks, batch requests, caches, and temporary download URLs

**Safe test pattern:**

1. Use two accounts or tenants you control.
2. Create one object under Account A.
3. Observe every identifier and reference used by the supported client.
4. Replay the same documented action as Account B, changing only the object reference.
5. Check read, update, delete, share, export, clone, attach, execute, and indirect-reference paths.
6. Minimize the proof and do not access data belonging to unrelated users.

A strong report proves cross-user or cross-tenant impact, not merely that an identifier is visible.

### 2.2 Incorrect role validation

Build a role-action matrix and verify authorization on the server for every action, transport, HTTP method, API version, asynchronous worker, and administrative path.

Roles to model may include:

- Anonymous, invited, suspended, deleted, free, paid, trial, and expired
- Member, viewer, editor, developer, workspace admin, billing admin, organization owner, and support
- Human user, service account, API token, connector identity, agent identity, and delegated identity

Questions to test:

- Does changing a client-supplied role, owner, tenant, plan, or permission field alter authority?
- Is the same action protected consistently across UI, REST, GraphQL, WebSocket, mobile, and legacy endpoints?
- Can an invitation, share link, API key, or delegated token be used outside its intended role or tenant?
- Does a background job re-check authorization when it executes, or only when it is queued?
- Can an agent or tool perform an action that the initiating user cannot perform directly?

### 2.3 Privilege escalation

Separate the analysis into:

- Horizontal escalation: one peer accesses another peer’s resources.
- Vertical escalation: a lower-privileged actor performs an administrator or owner action.
- Context-dependent bypass: an actor skips required workflow state or approval.
- Cross-tenant escalation: an identity in one organization reaches another organization’s assets.
- Delegation escalation: an agent, connector, or service token has more authority than the requesting user.

High-impact evidence includes unauthorized access to sensitive data, unauthorized administrative actions, cross-tenant control, durable permission changes, unauthorized tool execution, or access to secrets. Bugcrowd’s current taxonomy lists cross-tenant PII exposure, key leakage, full-system compromise, model extraction, training-data poisoning, and sensitive IDOR variants among top-priority AI or access-control issues.

---

## 3. AI-specific high-value vulnerability classes

### A. Prompt injection

Assess direct and indirect prompt injection only where the program allows it. Test whether untrusted instructions in user input, webpages, files, emails, tickets, retrieved documents, images, or tool results can override trusted instructions or cause unauthorized actions.

Impact must be demonstrated at the application boundary, such as unauthorized data access, unauthorized tool invocation, cross-tenant retrieval, secret disclosure, or unsafe state change. A model merely following an unusual prompt is often not enough.

### B. Sensitive information disclosure

Look for exposure of:

- Other users’ prompts, conversations, documents, memories, outputs, and feedback
- API keys, access tokens, connector credentials, internal URLs, environment data, or logs
- Training or retrieval data that the current actor is not authorized to receive
- Hidden configuration when disclosure creates a concrete security impact

System prompt leakage is an OWASP category, but bounty eligibility and impact vary by program, so the program policy controls.

### C. Excessive agency and tool authorization

Map each tool’s capabilities, credentials, scopes, side effects, approval requirements, and tenancy. Verify that user authorization is checked before every consequential action and again at execution time. Test whether untrusted content can cause an agent to select or parameterize a tool in a way the user did not authorize.

### D. Retrieval and vector-store weaknesses

Test ingestion authorization, source ownership, tenant filters, chunk-level metadata, index isolation, deletion propagation, stale caches, citations, permission changes, and retriever behavior. Look for unauthorized retrieval rather than harmless relevance errors.

### E. Improper output handling

Treat model output as untrusted. Review every place it is rendered, executed, parsed, queried, or passed to another component. Relevant sinks include HTML, Markdown, SQL, shell commands, templates, code interpreters, browser automation, URLs, file paths, tool arguments, and structured data parsers.

### F. Supply chain and model artifacts

Inventory third-party models, datasets, adapters, tokenizers, packages, containers, notebooks, and plugins. ModelScan is an open-source scanner aimed at unsafe code in model artifacts and documents support for H5, Pickle, and SavedModel formats.

### G. Data and model poisoning

Within explicit authorization, assess whether untrusted contributions can alter training, fine-tuning, retrieval, evaluation, feedback, or memory in a durable way. Focus on provenance, approval, isolation, rollback, and whether poisoned content affects other users or privileged workflows.

### H. Model extraction, resource abuse, and unbounded consumption

Review quotas, concurrency, batch jobs, retries, streaming, file limits, context length, recursive agents, tool loops, caching, and billing boundaries. Do not perform stress or denial-of-service testing unless the program explicitly permits it.

### I. Traditional vulnerabilities in AI products

Do not overlook classic classes: broken authentication, session flaws, injection, SSRF, file upload, path traversal, request smuggling, business-logic errors, race conditions, payment or quota bypass, secret exposure, cloud misconfiguration, and vulnerable dependencies. OWASP describes its web Top 10 as a reference standard for critical web-application risks.

---

## 4. Component inventory

For each target, create a system map containing:

- Entry points and clients
- Identities, roles, tenants, credentials, and trust boundaries
- APIs, endpoints, schemas, event streams, and background jobs
- Models, providers, gateways, versions, and routing rules
- Prompt layers and context assembly
- Retrieval sources, vector databases, embedding services, and metadata filters
- Agents, tools, connectors, plugins, MCP servers, and approval gates
- Data stores, caches, logs, telemetry, and export paths
- Upload, parsing, conversion, OCR, transcription, and media pipelines
- Training, fine-tuning, evaluation, feedback, and deployment pipelines
- Model registry, artifact store, package registry, containers, and CI/CD

MITRE ATLAS provides a living knowledge base of adversary tactics, techniques, mitigations, case studies, and AI threat matrices spanning predictive, generative, agentic, and enterprise AI.

---

## 5. File types worth recognizing

Never open untrusted model artifacts on your main machine. Use an isolated, disposable environment and static inspection first.

### Model and tensor artifacts

- `.pkl`, `.pickle`, `.joblib`, `.pt`, `.pth`, `.bin`
- `.safetensors`, `.onnx`, `.h5`, `.hdf5`, `.keras`
- TensorFlow SavedModel directories and protobuf files
- Adapter and quantization artifacts such as LoRA files and GGUF/GGML-family files

### Data and retrieval artifacts

- `.json`, `.jsonl`, `.csv`, `.tsv`, `.parquet`, `.arrow`
- `.txt`, `.md`, `.html`, `.xml`, `.yaml`, `.yml`
- `.pdf`, `.docx`, `.pptx`, `.xlsx`
- Images, audio, video, OCR output, captions, and transcripts

### Application and infrastructure artifacts

- OpenAPI/Swagger, GraphQL schemas, protobuf, and gRPC definitions
- `.env`, configuration files, manifests, lockfiles, SBOMs, Dockerfiles, Compose files, Helm charts, and Kubernetes YAML
- Jupyter notebooks, Python packages, JavaScript packages, browser extensions, mobile packages, and source maps
- Logs, traces, HAR files, cURL captures, and proxy project files

File extension alone does not establish safety. The parser, loader, conversion pipeline, and downstream execution behavior determine risk.

---

## 6. Tool stack

Use tools only on in-scope systems and within program rules.

### Traffic and API analysis

- Burp Suite or OWASP ZAP
- Browser developer tools
- cURL, HTTPie, Postman, or Insomnia
- GraphQL and WebSocket-capable clients
- Diffing tools for multi-account authorization tests

PortSwigger documents Burp workflows for IDOR, parameter-based access control, privilege escalation, and horizontal-access testing.

### Discovery and asset documentation

- Program policy and asset inventory
- DNS, certificate, repository, and endpoint discovery tools only where permitted
- OpenAPI, GraphQL, JavaScript, mobile, and desktop-client inspection
- Note-taking, screenshots, request/response capture, and evidence hashing

### AI and model security

- ModelScan for supported serialized model formats
- Dependency, container, secret, IaC, and SBOM scanners
- Prompt and evaluation harnesses that log exact inputs, outputs, model versions, temperatures, and tool traces
- Dataset validation, provenance checks, and duplicate/poisoning analysis
- Vector-store and retrieval test harnesses

### Automation

Automate comparison, replay, normalization, and evidence collection before automating aggressive discovery. Prefer deterministic scripts with strict rate limits, explicit target allowlists, redaction, and a kill switch.

---

## 7. Core workflow

### Phase 0: legal and program setup

1. Read scope and exclusions.
2. Record safe-harbor language, prohibited methods, rate limits, data rules, and disclosure requirements.
3. Create dedicated test identities and label all accounts and artifacts.
4. Define stop conditions.

HackerOne recommends clearly defined AI assets, AI-specific vulnerability scope, documentation, tooling, incentives, and a supportive testing environment for AI-focused bounty programs.

### Phase 1: architecture and threat model

1. Build the component inventory.
2. Draw identities, tenants, data flows, trust boundaries, and privilege changes.
3. Map conventional risks to OWASP Web risks and AI risks to OWASP LLM, OWASP AISVS, and MITRE ATLAS.
4. Rank hypotheses by plausible impact, reproducibility, scope safety, and novelty.

OWASP AISVS is a catalogue of testable requirements covering the AI lifecycle and defines three verification levels, with Level 2 aimed at production, customer-facing, personal-data, or consequential systems.

### Phase 2: build the authorization matrix

For every object and action, record:

- Actor and role
- Tenant and ownership
- Required permission
- Client and transport
- Endpoint or operation
- Object identifiers
- Expected result
- Actual result
- Side effect
- Evidence

Test read, list, search, create, clone, update, delete, share, export, import, execute, approve, cancel, retry, and restore.

### Phase 3: AI data-flow testing

Follow untrusted content through:
`input -> parser -> storage -> retrieval -> prompt assembly -> model -> tool selection -> external action -> rendering -> logs/feedback`

At every boundary, ask:

- Who supplied this data?
- Who can influence it later?
- Which identity processes it?
- Which tenant filters apply?
- Is it treated as data or instruction?
- Can it trigger a side effect?
- Is authorization rechecked?
- Is the output safely handled?

### Phase 4: validate impact safely

- Use your own accounts and synthetic data.
- Prove the smallest meaningful impact.
- Avoid persistence, service degradation, bulk collection, or access to unrelated users.
- Record exact timestamps, request IDs, model versions, parameters, and prerequisites.
- Remove test artifacts when safe and allowed.

### Phase 5: report

A strong report contains:

1. Clear title naming weakness and impact
2. Program asset and affected component
3. Severity rationale tied to concrete impact
4. Preconditions and test accounts
5. Minimal reproducible steps
6. Sanitized request/response evidence
7. Expected versus actual authorization behavior
8. AI-specific context, including model/tool/retrieval path
9. Impact and realistic abuse case
10. Remediation guidance
11. Cleanup notes

Some programs require one vulnerability per report and sufficient detail to reproduce; individual program rules always take precedence.

---

## 8. Reporting access-control bugs well

### Example title pattern

`Cross-tenant authorization bypass in [operation] allows a workspace member to [impact] another organization’s [resource]`

### Evidence checklist

- Account A and Account B are controlled by the researcher
- Their roles and tenant memberships are documented
- The protected object was created by A
- B’s unauthorized request is shown
- The server response and side effect are shown
- The proof avoids unrelated user data
- The control test shows the same request is valid for A
- The report explains why an identifier leak alone is not the finding

### Remediation themes

- Centralized, deny-by-default server authorization
- Object-level and tenant-level ownership checks
- Policy checks based on trusted server state, not client fields
- Authorization on every endpoint, method, API version, worker, and tool action
- Least-privilege tokens and per-user delegation
- Re-authorization at execution time for queued or agentic actions
- Immutable audit trails and tests for negative authorization cases

---

## 9. Learning path

### Foundation

- HTTP, cookies, sessions, OAuth/OIDC, JWT, CORS, browser security, REST, GraphQL, WebSockets
- Linux, networking, DNS, TLS, cloud basics, containers, Git, Python, JavaScript, SQL
- Authentication, authorization, tenancy, object ownership, business logic, race conditions

### Web and API practice

- PortSwigger Web Security Academy access-control material and labs on authorized, deliberately vulnerable targets.
- OWASP web and API guidance
- Local vulnerable applications and CTF-style labs

### AI foundation

- Tokens, context windows, inference, embeddings, vector similarity, RAG, fine-tuning, evaluation
- Agents, function calling, connectors, memory, multimodal processing, guardrails, and moderation
- Training and inference pipelines, model serialization, registries, and supply chains

### AI security

- OWASP Top 10 for LLM Applications 2025
- OWASP AI Testing Guide, released as version 1 on November 26, 2025.
- OWASP AISVS
- MITRE ATLAS
- NIST AI RMF and the Generative AI Profile

NIST describes the Generative AI Profile as a cross-sector companion to AI RMF 1.0 intended to help organizations incorporate trustworthiness considerations into AI design, development, use, and evaluation.

---

## 10. Rules that protect the researcher and users

- Test only explicitly authorized assets.
- Program policy overrides generic checklists.
- Use test accounts and synthetic data.
- Collect the minimum evidence necessary.
- Do not retain or share personal data, credentials, or secrets.
- Do not perform denial of service, social engineering, phishing, physical attacks, or destructive testing unless explicitly authorized.
- Do not publish before coordinated disclosure permits it.
- Respect duplicate rules and do not inflate a finding with unsafe impact demonstrations.
- Preserve raw evidence securely and provide redacted copies in the report.
- Separate security vulnerabilities from model-quality, policy, bias, or safety findings unless the program explicitly accepts those categories.

---

## 11. Research database structure

Create one record per hypothesis or finding with these fields:

- Program, asset, scope status, policy revision date
- Component, endpoint, model, provider, API version
- Vulnerability family and taxonomy mapping
- Actor, role, tenant, object, action
- Preconditions and test data
- Expected and actual result
- Impact, likelihood, severity, confidence
- Reproduction status and duplicate checks
- Evidence locations and hashes
- Report status, response, bounty, remediation, retest
- Lessons learned and reusable test case

---

## 12. First campaign: access control in AI applications

1. Choose one authorized AI application.
2. Create two users in separate tenants plus the lowest and highest available roles you are allowed to create.
3. Inventory every AI object and operation visible in the client.
4. Capture a normal request for each operation.
5. Build the actor-object-action matrix.
6. Test cross-user, cross-role, cross-tenant, expired-membership, shared-link, API-token, queued-job, and agent-tool paths.
7. Prioritize unauthorized read, write, execute, export, secret access, and durable permission changes.
8. Validate with synthetic content and the minimum proof.
9. Map the finding to the program’s severity rules and Bugcrowd VRT or CVSS only if the program uses them.
10. Submit a concise, reproducible report and preserve a regression test.

---

## 13. Recommended master taxonomy

Use these labels so notes are searchable:

- `AUTHN`, `AUTHZ`, `IDOR`, `TENANT`, `ROLE`, `PRIVESC`, `SESSION`, `OAUTH`
- `PROMPT-INJECTION`, `SENSITIVE-DATA`, `SYSTEM-PROMPT`, `OUTPUT-HANDLING`
- `AGENT`, `TOOL`, `CONNECTOR`, `MCP`, `RAG`, `VECTOR`, `MEMORY`
- `POISONING`, `MODEL-FILE`, `SUPPLY-CHAIN`, `MODEL-EXTRACTION`
- `QUOTA`, `COST`, `DOS`, `RACE`, `BUSINESS-LOGIC`
- `WEB`, `API`, `MOBILE`, `DESKTOP`, `CLOUD`, `CI-CD`

---

## Research status

This page is the initial baseline. The next useful expansion is a vulnerability-by-vulnerability test catalogue with safe test cases, evidence templates, likely false positives, severity signals, and report templates for each component class.
