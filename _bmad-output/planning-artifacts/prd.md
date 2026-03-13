---
stepsCompleted: [step-01-init, step-02-discovery, step-02b-vision, step-02c-executive-summary, step-03-success, step-04-journeys, step-05-domain, step-06-innovation, step-07-project-type, step-08-scoping, step-09-functional, step-10-nonfunctional, step-11-polish]
classification:
  projectType: api_backend
  domain: blockchain_web3
  complexity: high
  projectContext: greenfield
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-tao-gateway-2026-03-11.md
  - obsidian-vault/AI/kb/Bittensor/tao-gateway-plan.md
  - obsidian-vault/AI/kb/Bittensor/bittensor-subnet-registration-costs.xlsx
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/README.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/01-architecture.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/02-yuma-consensus.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/03-subnets.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/04-mining.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/05-validation.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/06-sdk-reference.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/07-synapse-protocol.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/08-tokenomics.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/09-governance.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/10-development-guide.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/11-project-opportunities.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/12-glossary.md
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 0
  projectDocs: 0
  coworkPlan: 1
  knowledgeBase: 13
  spreadsheets: 1
workflowType: 'prd'
date: 2026-03-11
author: Cevin
---

# Product Requirements Document - tao-gateway

**Author:** Cevin
**Date:** 2026-03-11

## Executive Summary

TaoGateway is a REST API gateway that exposes the Bittensor decentralized AI network as simple, OpenAI-compatible HTTP endpoints. Developers authenticate with an API key and send JSON payloads — no wallets, no staking, no blockchain knowledge required.

The Bittensor network hosts 128+ specialized subnets covering text generation, image generation, code generation, storage, search, and more. Today, consuming any of these capabilities requires the Python SDK, wallet management (coldkeys/hotkeys), understanding of metagraph mechanics, and async Dendrite/Synapse code. This locks out the vast majority of developers who just want an API call.

TaoGateway eliminates that barrier. The gateway translates REST requests into subnet-specific Synapse queries via Dendrite, selects high-quality miners using metagraph incentive data, and formats responses into familiar structures. Starting with SN1 (text generation), SN19 (image generation), and SN62 (code generation), the gateway is designed to eventually cover every viable subnet in the network.

The target users are ecosystem app builders who want to compose capabilities across subnets without duplicating Bittensor plumbing, and web2 developers who want decentralized AI through an interface they already know.

### What Makes This Special

The core differentiator is **compounding breadth**. Three initial subnets are table stakes — the real value emerges as adapter coverage grows. One API key unlocking 10, 30, 50+ specialized AI capabilities that no single centralized provider can match. Every new subnet adapter multiplies the value for every existing user.

The gateway is the first production-quality multi-subnet API gateway for Bittensor. No equivalent exists today — the project-opportunities analysis identifies this as a Tier 1 ecosystem gap. First-mover advantage matters: once developers wire their applications to these endpoints, switching cost is high.

The core is open-source (MIT licensed, public repo) — aligned with the ethos of a decentralized network. Business-sensitive logic (miner scoring algorithms, pricing strategies, operational configurations) stays private. Subnet teams can contribute adapters, and the community can self-host.

Per-request network cost to the gateway operator is zero — miners are compensated through TAO emissions, not per-query fees. Revenue is a per-request usage fee covering infrastructure margin. Pricing is usage-based: a free tier provides enough requests to build and test integrations, then developers pay per request at subnet-specific rates. No monthly subscriptions. Hotkey registration for the three MVP subnets costs ~0.002 TAO (~$0.37 at current prices).

## Project Classification

- **Project Type:** API / Backend Service (FastAPI, REST endpoints, authentication middleware, rate limiting)
- **Domain:** Blockchain / Web3 (deep Bittensor SDK integration — wallets, Dendrite, metagraph, Synapse protocol)
- **Complexity:** High (multi-subnet protocol translation, wallet security, chain state synchronization, miner quality tracking)
- **Project Context:** Greenfield (new codebase, no existing system)

## Success Criteria

### User Success

- **Time to first request:** New developer goes from signup to successful API response in under 5 minutes
- **Integration effort:** Ecosystem builder replaces SDK boilerplate with a single HTTP call
- **OpenAI compatibility:** Developer swaps `base_url` and existing code works without modification
- **Reliability:** >99% of requests return a valid response (accounting for miner availability)
- **Latency:** Gateway overhead adds <200ms p95 on top of miner response time

### Business Success

| Milestone | Target | Signal |
|---|---|---|
| 3-month | 100 registered developers, free tier active usage | Product-market fit signal |
| 6-month | 500 registered developers, revenue covers infrastructure (~$150/mo) | Self-sustaining |
| 12-month | 2,000 registered developers, consistent monthly profit ($500-1,000/mo after costs) | Growth validation |
| 18-month+ | Revenue supports full-time focus on TaoGateway and similar projects | Independence |

**Note:** These targets are intentionally conservative relative to the Product Brief projections. The brief modeled optimistic adoption ($15K MRR at 12 months); these targets reflect realistic solo-operator economics where covering infrastructure and generating modest profit validates the model before scaling.

- **Weekly active rate:** 30% of registered developers make at least 1 request in 7 days
- **Conversion rate:** Track % of free tier users who hit the cap and convert to paid
- **Community engagement:** GitHub stars, Discord mentions, PRs, adapter requests as ecosystem value signal

### Technical Success

- **Metagraph sync:** Stays fresh — gateway always has current miner state for routing decisions
- **Adapter extensibility:** Adding a 4th subnet adapter is straightforward, proving the pattern works
- **Wallet security:** Zero security incidents involving gateway-managed keys
- **Request success rate:** >99% measured end-to-end
- **Gateway latency overhead:** <200ms p95

### Measurable Outcomes

- **Differentiator metric:** Number of live subnet adapters is a first-class KPI — this is the compounding breadth that makes TaoGateway unique
- **Subnet coverage trajectory:** 3 (MVP) → 10 (6-month) → 50+ (12-month)
- **Per-adapter value:** Track requests per subnet to understand which capabilities drive the most usage

## Product Scope

### MVP — Minimum Viable Product

**API Gateway:**
- `/v1/chat/completions` — OpenAI-compatible text generation (SN1)
- `/v1/images/generate` — Image generation (SN19)
- `/v1/code/completions` — Code generation (SN62)
- `/v1/models` — List available subnets and capabilities
- `/v1/health` — Health check

**Subnet Adapters:**
- SN1 adapter: TextGenSynapse → Dendrite query → OpenAI-format response (including streaming via SSE)
- SN19 adapter: ImageGenSynapse → Dendrite query → image response
- SN62 adapter: CodeSynapse → Dendrite query → code response
- Base adapter pattern established for future subnet onboarding

**Infrastructure:**
- API key authentication (hashed keys, per-key rate limits)
- Redis rate limiter (token bucket, per-subnet limits)
- Basic miner selection using metagraph incentive scores
- PostgreSQL for API keys, usage records, miner scores
- Docker Compose for local dev
- Integration tests for all three endpoints

**Pricing & Rate Limiting:**
- Free tier with per-subnet limits (e.g., SN1: 10 req/min, 100/day, 1,000/month; SN19: 5/min, 50/day, 500/month)
- Usage-based paid tier at subnet-specific rates, higher rate limits, no daily/monthly caps

**Developer Dashboard:**
- API key management (create, rotate, revoke)
- Usage monitoring (requests, latency per subnet)
- Account overview

**MVP validated when:**
- Developer can sign up, get a key, and hit all three subnets in under 5 minutes
- >99% success rate on formatted responses
- 20+ developers actively using the API
- 4th subnet adapter is straightforward to add
- Gateway latency overhead <200ms p95

### Growth & Vision

See **Project Scoping & Phased Development** for the complete phased roadmap, including Phase 2 (Growth: Stripe billing, streaming, 10+ adapters) and Phase 3 (Expansion: universal subnet coverage, TAO-native payments, multi-subnet orchestration, SDK libraries).

## User Journeys

The following journeys illustrate how each user type interacts with TaoGateway, revealing requirements through concrete scenarios. Each journey ends with a "requirements revealed" summary that traces forward to the Functional Requirements section.

### Journey 1: Priya Discovers Decentralized AI

**Who:** Priya, fullstack developer building a SaaS product. Uses OpenAI today. Zero blockchain knowledge.

**Opening Scene:** Priya is evaluating AI providers for her content generation SaaS. She's paying OpenAI $200/mo and worried about vendor lock-in. A Hacker News comment mentions "decentralized AI alternatives." She googles "decentralized AI API" and finds TaoGateway's GitHub repo, which has a clean README with a curl example.

**Rising Action:** She clicks through to the docs site. Sees "OpenAI-compatible" in the first paragraph. Signs up — email, password, done. Dashboard shows her a fresh API key: `tao_sk_live_...`. The quickstart shows a curl command. She copies it, swaps in her key, hits enter. Response comes back in 2 seconds. She grins.

She opens her SaaS codebase, changes `base_url` from `api.openai.com` to `api.taogateway.com`, runs her test suite. 47 of 48 tests pass. One fails because she was using a GPT-4-specific parameter. She removes it. All green.

**Climax:** Priya deploys to staging. Her app works. She checks the TaoGateway dashboard — sees her request count, latency per subnet, and remaining free tier quota. She's used 200 of her 1,000 monthly free requests in an afternoon of testing.

**Resolution:** Her app is live on decentralized AI. She never created a wallet, never staked TAO, never read a word about metagraph mechanics. When she hits the free tier cap two weeks later, she adds a payment method and keeps going. Later she discovers `/v1/images/generate` and adds AI image features to her product — something she couldn't do through OpenAI's API alone.

**Requirements revealed:** Signup flow, API key generation, OpenAI-compatible endpoints, dashboard with usage monitoring, free tier enforcement, upgrade path to paid, documentation site with quickstart.

### Journey 2: Kai Composes Across Subnets

**Who:** Kai, an ecosystem developer building a multi-agent platform on Bittensor. Knows the SDK but is tired of managing Dendrite boilerplate for each subnet.

**Opening Scene:** Kai has a working prototype that queries SN1 for text generation. It took him 3 days to get the wallet setup, Dendrite initialization, and Synapse handling right. Now he needs to add SN62 for code generation. The thought of duplicating all that plumbing makes him groan. He sees TaoGateway mentioned in the Bittensor Discord by another builder.

**Rising Action:** Kai checks the GitHub repo. He recognizes the Bittensor concepts immediately — he sees the adapter pattern and understands what's happening under the hood. He signs up, gets a key, and replaces his 50 lines of Dendrite code with a single HTTP POST. Same result. He adds SN62 in 10 minutes — just a different endpoint and payload format.

**Climax:** Kai builds a pipeline: user prompt → SN1 generates a plan → SN62 generates code based on the plan. Two API calls, chained. What would have taken him a week of SDK integration takes an afternoon.

**Resolution:** Kai ships his multi-agent platform weeks ahead of schedule. As TaoGateway adds more subnet adapters, Kai gets new capabilities without writing any integration code. He starts thinking about SN19 for generating diagrams in his platform.

**Requirements revealed:** Multi-subnet access through single key, consistent API patterns across subnets, low-latency responses for chaining, `/v1/models` to discover available subnets, documentation per subnet adapter.

### Journey 3: Cevin Operates the Gateway

**Who:** Cevin, TaoGateway creator and sole operator. Running the infrastructure, monitoring health, managing the business.

**Opening Scene:** Morning check. Cevin opens the admin dashboard — sees overnight request volume, error rates per subnet, miner response times, and metagraph sync status. Everything green. A few new signups overnight from a Discord mention.

**Rising Action:** Mid-afternoon, the SN19 error rate spikes to 15%. Cevin checks the miner scores — three top miners on SN19 went offline simultaneously (probably a hosting issue). The gateway is falling back to lower-ranked miners with slower response times. He checks the metagraph sync — it's fresh, the offline miners already show reduced incentive scores. The gateway is auto-adapting, but latency is up.

**Climax:** A developer posts in Discord: "image gen seems slow today." Cevin checks the admin view, confirms it's a miner availability issue on the Bittensor side, not a gateway problem. He responds with context and an ETA based on when miners typically come back online.

**Resolution:** Miners recover by evening. Error rate drops back to <1%. Cevin reviews the incident — the gateway handled the degradation gracefully, but he notes that he wants better alerting (Slack notification when error rate exceeds threshold) and eventually a Discord agent that can auto-respond to common issues and escalate the rest.

**Future state:** An AI agent monitors Discord, answers common questions ("is SN19 down?" → checks health endpoint and responds), and pings Cevin only for issues requiring human judgment.

**Requirements revealed:** Admin dashboard (error rates, miner health, metagraph sync status, signup metrics), alerting system, miner score tracking, health monitoring, usage analytics, incident response tooling.

### Journey 4: Ridges Team Partners for Subnet Adoption

**Who:** The Ridges team (SN62 — code generation). They want more developers consuming their miners' outputs.

**Opening Scene:** The Ridges team lead sees TaoGateway mentioned in the Bittensor Discord. They check the GitHub repo and see SN1 and SN19 adapters already live. They reach out to Cevin: "We'd love to have SN62 on TaoGateway."

**Rising Action:** Cevin asks for their Synapse documentation — the CodeSynapse fields, expected input/output formats, any quirks in their protocol. The Ridges team sends their protocol spec and a few example requests/responses. Cevin builds the SN62 adapter using the established base pattern.

**Climax:** Cevin deploys the SN62 adapter and announces it in Discord. The Ridges team retweets / reshares. Within a week, they see increased query volume to their miners from TaoGateway users.

**Resolution:** The Ridges team sees more demand for their subnet, which drives staking interest and emission share under dTAO. They become advocates for TaoGateway and start referring other subnet teams. When they update their Synapse protocol, they proactively notify Cevin so the adapter stays current.

**Requirements revealed:** Clean adapter pattern (fast to build new adapters), subnet documentation ingestion, adapter versioning for protocol changes, announcement/changelog system, relationship management with subnet teams.

### Journey 5: Developer Hits Problems

**Who:** Marco, a developer integrating TaoGateway into his chatbot. Things aren't going smoothly.

**Opening Scene:** Marco signs up and gets his first SN1 request working. He's excited. He starts building his chatbot integration with higher request volume.

**Rising Action:** Marco's chatbot starts getting 429 (Too Many Requests) responses during peak usage. He checks the dashboard and sees he's hitting the free tier's 10 req/min limit on SN1. The error response includes a clear `Retry-After` header and a message pointing to the rate limits docs.

He upgrades to paid. Rate limits increase. But now he's getting occasional 504 timeouts on some requests. He checks the response headers — they include the miner UID that was queried. He notices timeouts correlate with specific miners.

**Climax:** Marco posts in Discord asking about the timeouts. The docs explain that miner availability varies (it's a decentralized network) and suggest retry logic. The response includes enough metadata (miner UID, latency, status) that he can build intelligent retry into his client.

**Resolution:** Marco adds a simple retry with exponential backoff. His chatbot runs reliably. He learns to check `/v1/health` and `/v1/models` to understand current subnet status before routing traffic. He appreciates that error responses are informative, not opaque.

**Requirements revealed:** Clear error responses with actionable information (rate limit headers, miner UIDs, status codes), health/status endpoints, comprehensive error documentation, response metadata for debugging, graceful degradation under miner unavailability.

### Journey 6: Security Engineer Reviews the Gateway

**Who:** Dana, a security engineer hired to audit TaoGateway before the public launch.

**Opening Scene:** Dana receives access to the codebase and a staging environment. Her brief: assess API key security, authentication flows, data handling, and the Bittensor wallet management layer.

**Rising Action:** Dana reviews the attack surface:
- **API key handling:** Keys stored as argon2 hashes. Key prefixes stored for identification. Keys transmitted via Authorization header over TLS. She checks for key leakage in logs — the gateway redacts keys in all log output.
- **Rate limiting:** Token bucket in Redis. She tests bypass attempts — concurrent requests, key rotation abuse, header manipulation. Rate limiter holds.
- **Wallet security:** The gateway's coldkey and hotkeys are stored on the server. She verifies they're not accessible via any API endpoint, not logged, not in environment variable dumps. She checks file permissions.
- **Input validation:** She sends malformed payloads, oversized requests, injection attempts in prompt fields. The gateway validates input schemas via Pydantic and returns 422 with field-level errors.

**Climax:** Dana finds that the miner response data is passed through to the API consumer without sanitization. A malicious miner could potentially inject content. She flags this for output sanitization.

**Resolution:** Dana delivers her report. Critical finding on output sanitization gets fixed before launch. She recommends additional hardening: request signing, API key scoping (restrict keys to specific subnets), and audit logging for all admin operations. These go into the security backlog.

**Requirements revealed:** Bcrypt key hashing, TLS enforcement, key redaction in logs, wallet file security, input validation (Pydantic schemas), output sanitization of miner responses, rate limit robustness, API key scoping, audit logging, security review process.

### Journey 7: QA Tester Validates the Gateway

**Who:** Alex, a QA tester validating TaoGateway before the MVP launch.

**Opening Scene:** Alex has the test plan: verify all three subnet endpoints work correctly, test rate limiting behavior, validate error handling, and run basic load tests.

**Rising Action:** Alex works through the test matrix:
- **Happy path per subnet:** Send valid requests to SN1, SN19, SN62. Verify response format matches the documented schema (OpenAI-compatible for SN1, image response for SN19, code response for SN62).
- **Rate limiting:** Hit the free tier limits. Verify 429 response with correct `Retry-After` header. Verify limits reset correctly. Test per-subnet independence (hitting SN1 limit doesn't affect SN19).
- **Error handling:** Invalid API key (401), malformed request body (422), nonexistent subnet (404), miner timeout (504). Verify each returns the correct status code and informative error body.
- **Edge cases:** Empty prompt, extremely long prompt, special characters, concurrent requests from same key.

**Climax:** Alex discovers that when all queried miners timeout on SN19, the gateway returns a generic 500 instead of a descriptive 504 with context about miner availability. He files the bug.

**Resolution:** Bug gets fixed — the gateway now distinguishes between internal errors and upstream miner failures, returning appropriate status codes and messages. Alex runs the regression suite. All green. He signs off on MVP readiness.

**Requirements revealed:** Comprehensive test suite (unit + integration), per-subnet response schema validation, rate limit testing, error code consistency, load testing infrastructure, regression test automation, distinction between gateway errors and upstream (miner) failures.

### Journey Requirements Summary

| Capability Area | Revealed By Journeys |
|---|---|
| Signup & API key management | Priya, Kai, Marco |
| OpenAI-compatible endpoints | Priya, Kai |
| Multi-subnet routing | Kai, Marco |
| Usage dashboard | Priya, Kai, Marco, Cevin |
| Admin/ops dashboard | Cevin |
| Rate limiting (per-subnet) | Marco, Alex |
| Error handling & response metadata | Marco, Dana, Alex |
| Miner selection & fallback | Cevin, Marco |
| Metagraph sync & health monitoring | Cevin, Alex |
| Wallet & key security | Dana |
| Input validation & output sanitization | Dana, Alex |
| Adapter pattern & extensibility | Kai, Ridges team, Alex |
| Documentation | Priya, Kai, Marco |
| Alerting & incident response | Cevin |
| Audit logging | Dana |

## Domain-Specific Requirements

### Bittensor Integration (Internal)

- **Wallet security:** Coldkey/hotkey management on the server. Coldkey encrypted at rest, minimal exposure. Separate operational hotkeys per subnet.
- **Chain state dependency:** Metagraph must stay synced via background process. Stale metagraph = routing to offline miners. Alerting on sync staleness.
- **Subnet protocol changes:** Subnets can update Synapse schemas. Pin adapters to Synapse versions, monitor subnet repos, integration tests per adapter.
- **Registration economics:** Hotkey registration costs are dynamic per subnet. Currently trivial (~0.002 TAO for 3 MVP subnets) but monitor for changes.
- **SDK dependency:** Pin Bittensor SDK version. Test upgrades in staging. Monitor release notes for breaking changes.

### API Security (External)

- **Threat model:** Public-facing REST API with bearer token auth. Primary attack vectors: key theft, rate limit bypass, malicious miner injection, input abuse.
- **Untrusted upstream:** Miner responses are untrusted by default — output sanitization required before returning to consumers.
- **Measurable security NFRs** defined in Non-Functional Requirements > Security (argon2 storage, TLS 1.2+, key redaction, dependency pinning).

### Data Privacy

- **Default:** Metadata only — timestamp, API key ID, subnet, endpoint, miner UID, latency, status code, token count. No request/response content stored.
- **Opt-in debug mode:** Developers can enable per-key content logging via dashboard. Request/response stored for 48 hours, then auto-deleted.
- **Quality scoring:** Computed in-memory from sampled responses (~5-10%). Only numeric scores persist, never content.
- **Policy:** Content is never associated with user identity for analytics. Docs state: "TaoGateway does not store your request or response content by default."

### Domain Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Coldkey compromise | TAO theft, loss of all subnet registrations | Encrypted storage, minimal on-server exposure, separate operational hotkeys |
| Metagraph sync failure | Routing to dead miners, high error rates | Background sync with health checks, fallback to cached state, staleness alerting |
| Subnet Synapse breaking change | Adapter stops working, 500 errors | Pin Synapse version, monitor subnet repos, integration tests per adapter |
| Malicious miner responses | Harmful/injected content to consumers | Output sanitization, response schema validation |
| Bittensor SDK breaking change | Gateway fails to start or query | Pin SDK version, test in staging, monitor release notes |
| Rate limit bypass | Gateway abuse, excessive network queries | Redis atomic token bucket, per-key and per-subnet enforcement |

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. First multi-subnet API gateway for Bittensor**
No production-quality gateway exists that normalizes multiple subnet protocols into a single REST API. This is a greenfield category, not an incremental improvement on an existing product.

**2. Decentralized-to-centralized protocol translation**
The adapter pattern translates between familiar REST/JSON and Bittensor's Dendrite/Synapse protocol — abstracting wallet management, metagraph mechanics, and subnet-specific Synapse schemas into standard HTTP. Each adapter handles a different protocol shape while presenting a consistent API surface.

**3. Zero upstream cost unit economics**
Unlike API proxies that pay per-request to upstream providers, TaoGateway's cost to query the Bittensor network is zero (miners compensated via TAO emissions). Revenue is pure infrastructure margin — a fundamentally better cost structure than any centralized API reseller.

**4. Quality routing on a permissionless network**
Miner availability and quality are variable by nature. The gateway must build its own quality intelligence (metagraph incentive scores initially, EMA-based scoring later) to route requests effectively on a network with no SLAs or guaranteed uptime.

### Market Context & Competitive Landscape

- **Chutes (SN64):** Serverless inference subnet — complementary, not competing. Single subnet, not a multi-subnet gateway.
- **Affine (SN120):** Subnet composition at the protocol level — deeper infrastructure, still requires Bittensor-native integration.
- **OpenRouter:** Multi-provider API routing for centralized LLMs — analogous model but for a completely different network.
- **No direct competitor:** The multi-subnet REST gateway for Bittensor is an unoccupied niche.

### Validation Approach

- **Pattern validation:** SN1 adapter proves the Dendrite/Synapse → REST translation works. If SN1 works, the pattern extends to SN19 and SN62.
- **Extensibility validation:** 4th subnet adapter should be straightforward to add — if it is, the architecture scales.
- **Economics validation:** Track actual infrastructure cost per request to confirm the zero-upstream-cost model holds in practice.
- **Adoption validation:** 100 developers in 3 months signals the gap is real and the solution is wanted.

### Risk Mitigation

| Innovation Risk | Fallback |
|---|---|
| Adapter pattern doesn't generalize to diverse subnets | Refactor to per-subnet custom endpoints (less elegant but functional) |
| Miner quality too variable for production use | Multi-miner querying (k-of-n), aggressive fallback, or focus on subnets with stable miners |
| Bittensor network changes break the translation layer | Pin SDK versions, maintain staging environment, active monitoring of protocol changes |
| Market too small (Bittensor ecosystem adoption) | Open-source release builds credibility even if hosted service doesn't scale; pivot to broader decentralized AI gateway |

## API-Specific Requirements

### Endpoint Specification

| Endpoint | Method | Subnet | Description |
|---|---|---|---|
| `/v1/chat/completions` | POST | SN1 | OpenAI-compatible text generation |
| `/v1/images/generate` | POST | SN19 | Image generation |
| `/v1/code/completions` | POST | SN62 | Code generation |
| `/v1/models` | GET | — | List available subnets and capabilities |
| `/v1/health` | GET | — | Gateway and subnet health status |
| `/v1/usage` | GET | — | Per-key usage statistics |

### Authentication Model

- **Mechanism:** Bearer token via `Authorization: Bearer tao_sk_live_...` header
- **Key format:** Prefixed (`tao_sk_live_`, `tao_sk_test_`) for environment identification
- **Storage:** Bcrypt-hashed in PostgreSQL; only key prefix stored in plaintext for lookup
- **Key lifecycle:** Create, rotate, revoke via developer dashboard
- **Future:** Optional subnet scoping (restrict keys to specific subnets)

### Data Schemas

- **Request/Response format:** JSON exclusively
- **OpenAI compatibility:** SN1 endpoint accepts and returns OpenAI ChatCompletion schema — existing `openai.ChatCompletion` clients work with `base_url` swap only
- **Validation:** Pydantic v2 models for all request/response schemas
- **Content types:** `application/json` for text/code endpoints; base64-encoded image data or URL for SN19 responses

### Error Response Codes

| Code | Meaning | When |
|---|---|---|
| 200 | Success | Valid response from miner |
| 401 | Unauthorized | Invalid or missing API key |
| 404 | Not Found | Unknown endpoint or subnet |
| 422 | Validation Error | Malformed request body (Pydantic field-level errors) |
| 429 | Rate Limited | Per-subnet or per-key limit exceeded (`Retry-After` header included) |
| 500 | Internal Error | Gateway-side failure |
| 502 | Bad Gateway | Miner returned invalid response |
| 504 | Gateway Timeout | Miner did not respond in time (includes miner UID in metadata) |

### Rate Limiting

- **Mechanism:** Redis token bucket with atomic Lua scripts
- **Scope:** Per-key, per-subnet enforcement
- **Free tier example:** SN1: 10 req/min, 100/day, 1,000/month; SN19: 5/min, 50/day, 500/month; SN62: 10/min, 100/day, 1,000/month
- **Paid tier:** Higher per-minute limits, no daily/monthly caps, subnet-specific rates
- **Headers:** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After` on 429

### API Versioning

- **Strategy:** URL-based versioning (`/v1/...`)
- **Breaking changes:** New version path (`/v2/`), previous version supported with deprecation notice for a defined period
- **Non-breaking changes:** Additive fields in responses, new optional query parameters — no version bump required
- **SDK/client libraries:** Deferred to post-MVP; the REST API is the primary interface

### API Documentation

- **Auto-generated:** FastAPI produces OpenAPI 3.0 spec and interactive docs at `/docs` (Swagger UI) and `/redoc`
- **Quickstart:** README with curl examples for each endpoint
- **Future:** Dedicated documentation site with per-subnet guides, SDK examples, and integration tutorials

### Implementation Considerations

- **Framework:** FastAPI with Pydantic v2 — chosen for async support, OpenAPI auto-generation, and alignment with Bittensor SDK (also Pydantic-based)
- **OpenAI client compatibility:** SN1 response schema must pass through `openai.ChatCompletion` parsing unchanged — this is a hard constraint
- **Response metadata:** All responses include gateway-specific headers (`X-TaoGateway-Miner-UID`, `X-TaoGateway-Latency-Ms`, `X-TaoGateway-Subnet`) for debugging and observability

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Platform MVP — prove the adapter pattern, developer experience, and multi-subnet value proposition. Learning goal: do developers want a unified REST gateway for Bittensor?

**Resource Requirements:** Solo developer (Cevin). Full-stack: FastAPI backend, Bittensor SDK integration, dashboard UI, infrastructure (Docker, PostgreSQL, Redis). Estimated 4-8 weeks focused effort.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Journey 1 (Priya — discovery & onboarding): Full support
- Journey 2 (Kai — multi-subnet composition): Full support
- Journey 3 (Cevin — operations): Basic support (monitoring, no alerting yet)
- Journey 5 (Marco — error handling): Full support

**Must-Have Capabilities:** See **Product Scope > MVP** for the complete feature list (endpoints, adapters, infrastructure, pricing, dashboard, validation criteria).

**Explicitly Deferred from MVP:**
- Payment processing / Stripe integration (free tier only at launch)
- EMA-based miner quality scoring (use metagraph incentive scores initially)
- Multi-miner querying (k-of-n)
- OAuth / advanced auth
- Documentation site (README + auto-generated /docs is sufficient)
- SDK client libraries
- Alerting system (Slack/Discord notifications)
- Discord agent for support
- API key subnet scoping

### Post-MVP Features

**Phase 2 (Growth — months 3-6):**
- Stripe integration for usage-based billing (paid tier)
- EMA-based miner quality tracking
- Additional subnet adapters (target 10+)
- Retry logic and fallback strategies
- Documentation site
- Alerting (Slack/Discord on error rate thresholds)
- Audit logging for admin operations

**Phase 3 (Expansion — months 6-12+):**
- Universal subnet coverage (50+ adapters)
- TAO-native payments
- Multi-subnet orchestration (chain calls)
- SDK libraries (Python, TypeScript, Go)
- Community adapter contributions
- Kubernetes deployment
- Prometheus + Grafana monitoring
- Discord support agent
- Load testing target: 1,000 req/s sustained

### Risk Mitigation Strategy

**Technical Risks:**
- *Metagraph sync staleness:* Background sync with configurable interval, health check on sync freshness, fallback to cached state. This is the highest-risk technical area — invest in monitoring early.
- *Adapter pattern generalization:* SN1 proves the pattern; SN19/SN62 as beta validates it extends. If it doesn't generalize, fall back to per-subnet custom endpoints.
- *Miner flakiness:* Accept higher variance at MVP (no multi-miner querying). Document in API docs that response times vary. Phase 2 adds retry/fallback.

**Market Risks:**
- *Distribution unknown:* Build-first approach. Organic distribution via GitHub, Bittensor Discord, subnet team partnerships. The open-source repo is the primary discovery surface.
- *Ecosystem size:* If Bittensor developer ecosystem is too small, open-source release still builds credibility. Pivot option: broaden to other decentralized AI networks.

**Resource Risks:**
- *Solo developer bottleneck:* Dashboard is the most cuttable piece if timeline pressure hits — API key management can fall back to CLI/API-only. Core gateway and adapters are non-negotiable.
- *Scope creep:* Phase boundaries are firm. No Phase 2 features sneak into MVP.

## Functional Requirements

### Developer Account Management
- FR1: Developer can create an account with email and password
- FR2: Developer can log in and access their dashboard
- FR3: Developer can view their account overview and current tier status

### API Key Management
- FR4: Developer can generate new API keys with environment-identifying prefixes
- FR5: Developer can view active API keys (masked, showing only prefix)
- FR6: Developer can rotate an API key (generate new, invalidate old)
- FR7: Developer can revoke an API key immediately

### Subnet Access — Text Generation (SN1)
- FR8: Developer can send text generation requests via OpenAI-compatible chat completions endpoint
- FR9: Developer can receive responses that work with existing OpenAI client libraries unchanged
- FR47: System supports streaming responses (SSE) for SN1 chat completions, compatible with OpenAI client stream=True

### Resource Management
- FR48: System cancels upstream miner queries when the client disconnects mid-request

### Subnet Access — Image Generation (SN19)
- FR10: Developer can send image generation requests with prompt text, resolution, and style parameters
- FR11: Developer can receive generated image data as base64-encoded PNG or image URL in the response

### Subnet Access — Code Generation (SN62)
- FR12: Developer can send code generation requests with prompt, target programming language, and optional context
- FR13: Developer can receive generated code as a string with language identifier in the response

### Subnet Discovery & Health
- FR14: Developer can list all available subnets and their capabilities
- FR15: Developer can check health status of each subnet
- FR16: Developer can view per-subnet availability percentage and p50/p95 response time metrics

### Usage Monitoring
- FR17: Developer can view their request counts per subnet over time
- FR18: Developer can view p50, p95, and p99 latency metrics per subnet
- FR19: Developer can view their remaining free tier quota per subnet
- FR20: Developer can view their usage history with daily granularity for the last 90 days

### Rate Limiting
- FR21: System enforces per-subnet, per-key request rate limits
- FR22: System returns rate limit status in response headers on every request
- FR23: System returns actionable error with retry timing when rate limit is exceeded

### Error Handling & Debugging
- FR24: System returns distinct error codes for gateway errors vs. upstream miner failures
- FR25: System includes miner identifier and latency metadata in response headers
- FR26: System returns field-level validation errors for malformed requests
- FR27: Developer can enable per-key debug mode for temporary request/response content logging

### Miner Routing
- FR28: System selects miners based on metagraph incentive scores
- FR29: System maintains metagraph state within 5 minutes of current via background synchronization
- FR30: System detects and avoids routing to offline or unresponsive miners

### Security
- FR31: System authenticates all API requests via bearer token
- FR32: System stores API keys using industry-standard one-way hashing (never plaintext)
- FR33: System redacts API keys from all log output
- FR34: System validates all request input against defined schemas
- FR35: System sanitizes miner response content before returning to developer
- FR36: System enforces TLS on all API endpoints

### Operator Administration
- FR37: Operator can view request volume, error rates, and latency across all subnets
- FR38: Operator can view metagraph sync status and freshness
- FR39: Operator can view new signups, weekly active developers, and requests per developer
- FR40: Operator can view miner response quality scores

### Data Privacy
- FR41: System logs request metadata only (no content) by default
- FR42: System auto-deletes debug mode content logs after 48 hours
- FR43: System computes quality scores in-memory without persisting request/response content

### API Documentation
- FR44: Developer can access auto-generated OpenAPI documentation with interactive request testing

### Extensibility
- FR45: Operator can add support for a new subnet without modifying core gateway code
- FR46: System supports subnet-specific request/response schemas through a consistent translation interface

## Non-Functional Requirements

### Performance

- **Gateway overhead:** <200ms p95 added latency for text (SN1) and code (SN62) endpoints
- **Image generation overhead:** <500ms p95 gateway overhead for SN19 (miner-side generation time is separate and variable)
- **API key validation:** <10ms per request (hash comparison cached via token lookup)
- **Rate limit check:** <5ms per request (atomic cache operation)
- **Metagraph sync:** Background process completes within 30 seconds, does not block request handling
- **Dashboard page load:** <2 seconds for any dashboard view as measured by server response time plus client render (DOMContentLoaded)
- **Concurrent requests:** Support 50 concurrent requests per gateway instance at MVP

### Security

- **API key storage:** Cryptographically hashed (one-way), never stored or logged in plaintext
- **Wallet protection:** Coldkey encrypted at rest, hotkeys isolated per subnet, neither exposed via any API endpoint or log output
- **Transport:** TLS 1.2+ required on all endpoints, no plaintext HTTP
- **Input validation:** All request payloads validated against defined input schemas before processing
- **Output sanitization:** All miner responses validated against expected schema before returning to developer
- **Key redaction:** API keys, wallet keys, and sensitive credentials redacted from all log output and error responses
- **Dependency security:** Pin all dependencies, monitor for known vulnerabilities

### Scalability

- **MVP capacity:** Single instance supports 100 active developers averaging 50 requests/day each (5,000 requests/day total)
- **Growth path:** Stateless request handling (no session affinity) so horizontal scaling is possible without architectural changes
- **Database:** Schema designed for partitioning by time if usage records grow large
- **Rate limiting:** Distributed cache, separated from application state — scales independently

### Reliability

- **Gateway uptime target:** 99.5% (best effort, ~3.6 hours downtime/month acceptable)
- **Miner failure isolation:** Individual miner timeouts do not cascade to gateway-wide failures
- **Metagraph staleness:** If sync fails, gateway continues operating on cached state with staleness indicator in health endpoint
- **Data durability:** Usage records and API keys backed by persistent storage with daily backups and point-in-time recovery capability
- **Graceful degradation:** If a subnet's miners are all unavailable, that subnet returns 503 with clear message; other subnets unaffected

### Integration

- **Bittensor SDK:** Pin to specific version, test upgrades in staging before production deployment
- **Metagraph dependency:** Gateway must handle metagraph API unavailability gracefully (cached fallback)
- **OpenAI compatibility:** SN1 responses must pass through `openai.ChatCompletion` client parsing — this is a hard integration constraint validated by automated tests

### Data Retention

- **Usage records (detailed):** 90-day retention — per-request metadata (key ID, subnet, timestamp, status, latency, tokens)
- **Usage records (aggregated):** Indefinite — daily/weekly summaries per key, per subnet
- **Debug content logs:** 48-hour TTL, auto-deleted
- **Miner quality scores:** Rolling 30-day window of scored observations
- **Retention policy evolution:** May move to rolling window for detailed records as data patterns become clear
