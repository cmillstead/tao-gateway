---
stepsCompleted: [1, 2, 3, 4, 5, 6]
status: complete
inputDocuments:
  - obsidian-vault/AI/kb/Bittensor/tao-gateway-plan.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/01-architecture.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/02-yuma-consensus.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/03-subnets.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/04-mining.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/05-validation.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/06-sdk-reference.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/07-synapse-protocol.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/08-tokenomics.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/10-development-guide.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/11-project-opportunities.md
  - obsidian-vault/AI/kb/Bittensor/knowledge-base/12-glossary.md
date: 2026-03-11
author: Cevin
---

# Product Brief: tao-gateway

## Executive Summary

TaoGateway is a developer-friendly REST API gateway that abstracts the entire Bittensor network into simple, OpenAI-compatible endpoints. No wallets, no staking, no blockchain knowledge required — just an API key and a JSON payload.

Starting with text generation (SN1), image generation (SN19), and code generation (SN62), the gateway aims to become the universal access layer for every Bittensor subnet. It's the HTTP on-ramp that the network doesn't have yet.

Built by a long-time Bittensor investor and community member, TaoGateway is open-source infrastructure designed to unlock the network's intelligence for any developer — whether they're building within the ecosystem or coming from web2 with no crypto background.

---

## Core Vision

### Problem Statement

Bittensor has a powerful decentralized network of AI capabilities — LLMs, image generation, code generation, storage, search, and more — spread across 128+ specialized subnets. But consuming these capabilities requires installing the Python SDK, creating and managing wallets (coldkeys, hotkeys), understanding registration, staking, and metagraph mechanics, and writing async code to query Axon endpoints directly.

This locks out the vast majority of developers who just want an API call.

### Problem Impact

The network's intelligence is effectively inaccessible to anyone who isn't deep in the Bittensor ecosystem. Web2 developers — the largest potential user base — can't use Bittensor at all without significant blockchain knowledge. Even developers building within the ecosystem face friction when they need to compose capabilities across subnets. The result: subnets operate in isolation, adoption stays low, and the network's collective intelligence goes underutilized.

### Why Existing Solutions Fall Short

- **Raw SDK**: Requires Python, wallet management, understanding of metagraph/dendrite/synapse patterns — too much overhead for application developers
- **Chutes (SN64)**: A serverless inference subnet, not a multi-subnet gateway. Complementary, not competing — TaoGateway could route through Chutes for certain workloads
- **Affine (SN120)**: Tackling subnet composition at the protocol level, but still requires Bittensor-native integration
- **No universal REST gateway exists**: The project-opportunities analysis identifies this as a Tier 1 gap in the ecosystem

### Proposed Solution

A REST API gateway that sits between developers and the Bittensor network, translating simple HTTP requests into subnet-specific Synapse queries via Dendrite, then formatting responses back into familiar formats (OpenAI-compatible where applicable).

The gateway handles authentication, miner selection, quality tracking, rate limiting, and billing — all the infrastructure concerns that developers shouldn't have to think about.

The adapter architecture is designed for comprehensive subnet coverage, with the goal of supporting every viable subnet over time. Each subnet gets an adapter that translates between the REST API format and that subnet's Synapse protocol.

### Key Differentiators

1. **OpenAI-compatible**: Developers swap one line of code to switch from OpenAI to TaoGateway for text generation
2. **Multi-subnet, single API key**: Text, image, code, and eventually every subnet through one gateway
3. **Smart miner routing**: Gateway learns which miners produce the best results and routes accordingly
4. **Complementary to the ecosystem**: Works with subnets like Chutes and Affine, not against them — amplifies the network rather than competing with it
5. **Open-source core**: MIT licensed, self-hostable, community-driven — built by a community member for the community
6. **First mover**: No production-quality multi-subnet API gateway exists today
7. **Universal ambition**: Not limited to 3 subnets — designed to eventually cover the entire network

---

## Target Users

### Primary Users

**Kai — The Ecosystem App Builder**

A developer building applications within the Bittensor ecosystem. Kai is working on a multi-agent platform that needs text generation from SN1 and code generation from SN62. He knows the SDK well enough to query one subnet, but integrating multiple subnets means duplicating wallet management, dendrite setup, and response handling for each one. He's spending more time on Bittensor plumbing than on his actual product.

- **Current pain**: Writing and maintaining dendrite boilerplate for every subnet integration. Dealing with miner selection, timeout handling, and response parsing per subnet.
- **What he wants**: One API call per capability. Focus on building his app, not managing Bittensor infrastructure.
- **Aha moment**: Swaps 50 lines of SDK code for a single HTTP POST and gets the same result.
- **Long-term value**: As TaoGateway adds more subnet adapters, Kai gets new capabilities without writing new integration code.

**Priya — The Web2 Developer**

A fullstack developer building a SaaS product who wants to add AI capabilities. She's evaluated OpenAI and Anthropic but is curious about decentralized alternatives — lower cost, no vendor lock-in, open-source ethos. She has zero blockchain knowledge and no interest in acquiring it. She wants an API that looks like what she already knows.

- **Current pain**: Bittensor sounds interesting but the onboarding wall is insurmountable — wallets, staking, Python SDK, metagraph concepts. She moves on within 5 minutes.
- **What she wants**: `pip install taogateway` or just a REST endpoint. OpenAI-compatible so she can swap her existing client with one line.
- **Aha moment**: Changes `base_url` from `api.openai.com` to `api.taogateway.com` and her app works with Bittensor-powered AI.
- **Long-term value**: Access to capabilities no centralized provider offers — image gen, code gen, and eventually 128 subnets of specialized AI through one key.

### Secondary Users

**Subnet Teams — Distribution Partners**

Subnet owners and development teams who want broader adoption of their subnet's capabilities. When TaoGateway writes an adapter for their subnet, every gateway user instantly becomes a potential consumer of their miners' outputs. They're not API users themselves, but they benefit from the gateway's existence and may contribute adapter code or documentation.

- **Value**: Increased demand for their subnet's miners, which drives staking interest and emission share under dTAO.
- **Interaction**: Collaborate on adapter development, provide Synapse documentation, potentially fund adapter creation.

### User Journey

**Discovery** → Developer finds TaoGateway through Bittensor Discord, GitHub, or searching for "Bittensor API" / "decentralized AI API"

**Onboarding** → Sign up, get an API key, make first request in under 5 minutes. Docs show a curl example that works immediately.

**Core Usage** → Integrate into their application. Use `/v1/chat/completions` like they would OpenAI. Explore other subnets through `/v1/models`.

**Success Moment** → Their app is live, powered by decentralized AI, and they never had to touch a wallet or understand metagraph mechanics.

**Long-term** → As new subnet adapters ship, they gain new capabilities through the same API key. Gateway becomes their default interface to the Bittensor network.

---

## Success Metrics

### User Success Metrics

- **Time to first request**: New developer goes from signup to successful API response in under 5 minutes
- **Integration effort**: Ecosystem builder replaces SDK boilerplate with a single HTTP call
- **Reliability**: >99% of requests return a valid response (accounting for miner availability)
- **Latency**: Gateway overhead adds <200ms on top of miner response time

### Business Objectives

**3-month (Phase 1 complete):**
- Working gateway with SN1, SN19, SN62 adapters
- 100+ registered developers
- Mentioned in Bittensor Discord as a known tool

**6-month:**
- 500+ registered developers
- 10+ subnet adapters live
- Community contributions (PRs, adapter requests, bug reports) as signal of ecosystem value

**12-month:**
- 2,000+ registered developers
- Comprehensive subnet coverage
- Self-sustaining via paid tiers (covering infrastructure costs at minimum)

### Key Performance Indicators

| KPI | Target | Measurement |
|-----|--------|-------------|
| Registered developers | 100 / 500 / 2,000 (3/6/12 mo) | API key signups |
| Active developers (weekly) | 30% of registered | At least 1 request in 7 days |
| Subnet coverage | 3 → 10 → 50+ adapters | Adapters shipping |
| Request success rate | >99% | Successful responses / total requests |
| Gateway latency overhead | <200ms p95 | Time from request receipt to dendrite call |
| Community engagement | Growing | GitHub stars, Discord mentions, PRs |

### Sustainability Model

- **Months 1-6**: Single-instance infrastructure (~$65-85/mo). Free tier only. Out-of-pocket.
- **Month 6 (before enabling paid tiers)**: Add failover — second API instance, DB replica, Redis replica (~$130-180/mo).
- **Break-even**: ~5-6 paid users at $29/mo covers failover-grade infrastructure.
- **Month 12+**: Usage-based pricing layer. Multi-instance scaling. Revenue covers infrastructure with margin.
- **Registration**: ~8.2 TAO one-time for all subnet hotkeys.
- **Per-request network cost**: Zero. Miners are compensated through TAO emissions, not per-query fees. Gateway margin is revenue minus infrastructure only.

---

## MVP Scope

### Core Features (Phase 1 — Launch)

**API Gateway:**
- `/v1/chat/completions` — OpenAI-compatible text generation (SN1)
- `/v1/images/generate` — Image generation (SN19)
- `/v1/code/completions` — Code generation (SN62)
- `/v1/models` — List available subnets and capabilities
- `/v1/health` — Health check endpoint

**Subnet Adapters:**
- SN1 adapter: TextGenSynapse → dendrite query → OpenAI-format response
- SN19 adapter: ImageGenSynapse → dendrite query → image response
- SN62 adapter: CodeSynapse → dendrite query → code response
- Base adapter pattern established for future subnet onboarding

**Infrastructure:**
- API key authentication (hashed keys, per-key rate limits)
- Redis rate limiter (token bucket)
- Basic miner selection using metagraph incentive scores
- PostgreSQL for API keys, usage records, miner scores
- Docker Compose for local dev (gateway + postgres + redis)
- Integration tests that hit all three endpoints

**Developer Dashboard:**
- API key management (create, rotate, revoke)
- Usage monitoring (requests, tokens, latency per subnet)
- Account overview

**Implementation order:** SN1 adapter first (prove the pattern), then SN19 and SN62 follow the same pattern. Dashboard in parallel or immediately after API is stable.

### Out of Scope for MVP

- **Billing / Stripe integration** — Free tier only at launch
- **Streaming responses (SSE)** — Adds complexity, defer to Phase 2
- **Advanced miner quality tracking** — Use metagraph incentive scores initially; EMA-based quality scoring is Phase 2
- **Multi-miner querying per request** — Query single best miner first; redundant k-of-n querying is Phase 2
- **Kubernetes / production hardening** — Docker Compose is sufficient for early traffic
- **User registration / OAuth** — API keys issued manually or via simple signup; full auth system is Phase 2
- **TAO-native payments** — Phase 5 per the Cowork plan
- **SDK libraries (Python, TypeScript, Go)** — Community can use raw HTTP initially

### MVP Success Criteria

The MVP is validated when:
- A developer can sign up, get an API key, and make a successful request to all three subnets in under 5 minutes
- The gateway reliably returns formatted responses with >99% success rate
- At least 20 developers are actively using the API (early adopter validation)
- The adapter pattern works cleanly enough that adding a 4th subnet is straightforward
- Gateway latency overhead is <200ms p95

**Go/no-go for Phase 2:** If 100+ developers have signed up within 3 months and weekly active rate is >20%, proceed with paid tiers and advanced features.

### Future Vision

**Phase 2 — Quality + Scale:**
- Streaming responses (SSE, OpenAI-compatible)
- EMA-based miner quality tracking from gateway observations
- Multi-miner querying (k-of-n, return best response)
- More subnet adapters (target 10+)
- Retry logic and fallback strategies

**Phase 3 — Monetization + Growth:**
- Stripe integration (paid tiers: $29/$99/enterprise)
- Failover infrastructure (DB replica, second API instance)
- Full auth system with OAuth
- Documentation site

**Phase 4 — Production Hardening:**
- Kubernetes deployment
- Prometheus + Grafana monitoring
- Load testing (target 1000 req/s)
- Security audit
- Open-source release (MIT)

**Phase 5 — Ecosystem Expansion:**
- Universal subnet coverage (50+ adapters)
- TAO-native payments
- Multi-subnet orchestration (chain SN1 → SN62 in one call)
- SDK libraries
- Subnet marketplace for community-contributed adapters
