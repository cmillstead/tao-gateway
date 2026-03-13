---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-tao-gateway-2026-03-11.md
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/prd-validation-report.md
  - _bmad-output/planning-artifacts/architecture.md
  - obsidian-vault/AI/kb/Bittensor/tao-gateway-plan.md
  - obsidian-vault/AI/kb/Bittensor/tao-agent-plan.md
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
---

# UX Design Specification tao-gateway

**Author:** Cevin
**Date:** 2026-03-12

---

<!-- UX design content will be appended sequentially through collaborative workflow steps -->

## Executive Summary

### Project Vision

TaoGateway is a REST API gateway that makes the Bittensor decentralized AI network accessible through simple HTTP endpoints — no wallets, no staking, no blockchain knowledge required. The product has two distinct surfaces: a public API (OpenAI-compatible endpoints consumed programmatically) and a developer dashboard (React SPA for account management, API keys, and usage monitoring). The API is the core product; the dashboard is the supporting tool that enables self-service developer operations.

### Target Users

**Priya (Web2 Developer)** — Zero blockchain knowledge. Uses OpenAI today. Wants to swap `base_url` and have things work. Needs the dashboard to be immediately familiar — no crypto jargon, no Bittensor concepts unless she goes looking. Success moment: changes one line of code and her app runs on decentralized AI.

**Kai (Ecosystem Builder)** — Knows Bittensor, tired of SDK boilerplate for every subnet integration. Wants multi-subnet access through one API key. Appreciates seeing subnet-level detail (miner UIDs, latency) in the dashboard but doesn't need hand-holding. Success moment: replaces 50 lines of Dendrite code with a single HTTP POST.

**Cevin (Operator)** — Sole operator running infrastructure. Needs an admin view: error rates per subnet, miner health, metagraph sync status, signup metrics, request volume. This is a separate concern from the developer-facing dashboard.

### Key Design Challenges

1. **Two audiences, one dashboard** — Priya wants simplicity and OpenAI-familiar patterns. Kai wants subnet-level granularity. The dashboard must be clean by default but expose depth on demand through progressive disclosure.

2. **"Time to first request" is the north star UX metric** — The entire onboarding flow (signup → dashboard → API key → docs → working curl) must complete in under 5 minutes. Any unnecessary step, confusing label, or missing affordance is a developer lost.

3. **Abstracting complexity without hiding it** — The value prop is "no blockchain knowledge needed," but power users want to see miner UIDs, subnet health, and network-level detail. The UX must layer information progressively — simple surface, rich depth.

4. **Operator dashboard separation** — Admin views (error rates, miner health, metagraph sync, signup metrics) serve a different user with different needs. Requires clear separation from the developer-facing dashboard without building a second application.

### Design Opportunities

1. **"First request" guided experience** — After signup and key creation, an inline quickstart showing a working curl/Python snippet with the developer's actual API key pre-filled. This is the conversion moment — the fewer steps between key creation and a working response, the better.

2. **Subnet-as-capability framing** — Instead of "SN1, SN19, SN62" (meaningless to Priya), frame as "Text Generation, Image Generation, Code Generation" with subnet IDs as secondary detail for ecosystem users. Makes the multi-subnet value prop immediately tangible.

3. **Usage visualization as value demonstration** — Usage graphs showing requests across subnets reinforce the "one key, many capabilities" differentiator. Every time a developer checks their dashboard, they see the breadth of what they're accessing through a single integration.

## Core User Experience

### Defining Experience

TaoGateway's core experience is defined by a single interaction pattern: **signup → API key → working request in under 5 minutes**. Everything else in the dashboard exists to support and extend that initial success.

The dashboard is not the product — the API is. Developers spend 95% of their time making programmatic requests from their own code. They visit the dashboard to create/manage keys, check usage and quota, and troubleshoot. The dashboard must be efficient and informative, never a destination in itself.

The most frequent dashboard action post-onboarding is **checking usage and quota status** — "am I hitting my limits?" needs to be answerable at a glance.

### Platform Strategy

**Primary platform:** Web dashboard, desktop-first (mouse/keyboard). Developers integrate APIs from their workstations.

**Responsive but not mobile-optimized:** The dashboard should render acceptably on tablets/phones but doesn't need mobile-specific UX. No developer is managing API keys from their phone at MVP.

**No offline requirements:** Live API management tool — always connected.

**API surface is platform-agnostic:** Any HTTP client, any programming language. The dashboard's quickstart must reflect this by showing curl (universal) and Python (OpenAI client swap) examples at minimum.

### Effortless Interactions

1. **API key creation** — One click to generate. Key displayed once with prominent copy-to-clipboard. No form fields, no configuration wizard. Create → copy → done.

2. **Quickstart snippet** — Auto-populated with the developer's actual API key. Copy, paste into terminal, hit enter, see a response. Zero editing required.

3. **Usage at a glance** — Dashboard landing shows current quota consumption per subnet as simple progress bars or counters. No clicks required to answer "am I near my limit?"

4. **Subnet discovery** — Capabilities framed as "Text Generation," "Image Generation," "Code Generation" — not SN1, SN19, SN62. Subnet IDs available as secondary detail for ecosystem users. Health status (available/degraded/down) visible inline.

5. **Key rotation** — Generate new key and revoke old in a single flow. No separate revocation step that developers forget.

### Critical Success Moments

1. **"It works" (Conversion moment)** — Developer runs the quickstart curl with their real API key and gets an AI-generated response back. This is the single most important UX moment in the entire product. If this fails or confuses, nothing else matters.

2. **"One key, three capabilities" (Differentiation moment)** — Developer sees Text, Image, and Code generation all available through the same API key on the dashboard or `/v1/models` response. The multi-subnet value prop becomes tangible — this is something OpenAI doesn't offer.

3. **"I'm not thinking about blockchain" (Absence-as-success moment)** — Priya completes onboarding, makes requests, checks usage, and never encounters a Bittensor-specific term she doesn't understand. The UX win is the absence of complexity. If she never has to Google "metagraph" or "subnet," we've succeeded.

4. **"My app is live on decentralized AI" (Pride moment)** — Developer deploys to production using TaoGateway. The dashboard shows real traffic flowing. They've adopted decentralized AI infrastructure without the overhead.

### Experience Principles

1. **Familiarity over novelty** — Mirror patterns developers already know (OpenAI dashboard, Stripe dashboard, Vercel dashboard). Innovation is in the API's capabilities, not the dashboard's interaction patterns. Don't make developers learn a new dashboard paradigm.

2. **Show capabilities, hide infrastructure** — Present subnets as capabilities (Text, Image, Code), not as blockchain constructs. Bittensor details (miner UIDs, metagraph state) are available for power users but never required for basic operation.

3. **Fastest path to value** — Every screen should answer: "what's the shortest path from here to a working API call?" Remove steps, pre-fill fields, auto-generate snippets. The dashboard exists to reduce friction, not to impress.

4. **Progressive disclosure** — Simple by default, detailed on demand. Usage shows totals first, per-subnet breakdown on click. Health shows green/yellow/red first, miner-level detail on drill-down. Priya sees a clean surface; Kai can dig as deep as he wants.

5. **Transparency over abstraction at the API level** — Response headers expose gateway internals (miner UID, latency, subnet) for debugging. Error messages are specific and actionable. The dashboard may hide complexity, but the API never lies about what happened.

## Desired Emotional Response

### Primary Emotional Goals

**Empowered and efficient** — "This just works. I'm not fighting the tool. I'm building." Developers should feel capable, not charmed. The emotional goal is competence amplification — the dashboard and API make developers feel like they're moving fast and making good decisions.

**Confident and trusting** — New API provider plus crypto ecosystem creates a double trust barrier. Every interaction must reinforce professionalism, reliability, and transparency. The developer should never question whether TaoGateway is production-ready.

**In control** — Developers should always know where they stand: quota remaining, request status, what went wrong and why. No surprises, no ambiguity, no hidden state.

### Emotional Journey Mapping

| Stage | Desired Feeling | Design Implication |
|-------|----------------|-------------------|
| **Discovery** | Curiosity + Relief — "Finally, a simple way to use Bittensor" | Clean README, working curl example on first page, no blockchain jargon in marketing |
| **Signup + First Key** | Confidence — "This is professional, I trust it with my project" | Minimal signup form, immediate key generation, polished dashboard UI |
| **First API Request** | Satisfaction + Mild surprise — "That was fast. It actually works." | Pre-filled quickstart snippet, fast response time, clear success feedback |
| **Integration into app** | Flow state — Tool disappears, developer focuses on their code | OpenAI-compatible interface, predictable behavior, good error messages |
| **Checking usage** | In control — "I know exactly where I stand" | At-a-glance quota bars, clear per-subnet breakdown, no math required |
| **Something breaks** | Informed calm — "I can see what went wrong and what to do" | Specific error codes, miner UID in headers, actionable error messages with retry guidance |
| **Returning** | Familiarity — "I know where everything is" | Stable UI, consistent navigation, dashboard state persists |

### Micro-Emotions

**Confidence over confusion** — The most critical emotional axis. Developer tools that create confusion lose users instantly. Every label, error message, and flow must reinforce "you're in the right place, doing the right thing." When in doubt between showing more information and showing less, show less with a path to more.

**Trust over skepticism** — The crypto ecosystem carries baggage — scams, vaporware, broken projects. TaoGateway must signal professionalism through clean design, clear status indicators, transparent pricing, and consistent behavior. The dashboard should feel like Stripe, not like a DeFi app.

**Accomplishment over frustration** — The "it works" moment after the first request is the emotional peak. Every design decision in the onboarding flow should protect this moment. If the first request fails, the error must be so clear that the developer can fix it in one try.

**Emotions to actively avoid:**
- **Overwhelm** — Too many options, too much information on first visit. Progressive disclosure prevents this.
- **Uncertainty** — Unclear pricing, vague errors, ambiguous quota status. Explicit numbers and clear labels prevent this.
- **Embarrassment** — Developer can't figure out something obvious. Familiar patterns and good defaults prevent this.
- **Abandonment anxiety** — "Is this project maintained? Will it disappear?" Active health status, recent changelog, responsive error handling signal liveness.

### Design Implications

| Emotional Goal | UX Design Approach |
|---------------|-------------------|
| Confidence | Familiar dashboard patterns (OpenAI/Stripe-like), consistent typography, professional color palette, no playful/casual design language |
| Trust | Health status always visible, transparent quota display, clear pricing page, professional error responses (not cute 404 pages) |
| Efficiency | Minimal clicks to key actions, no unnecessary confirmation dialogs, keyboard-friendly, fast page loads |
| Control | Real-time usage counters, explicit rate limit headers, per-subnet status, exportable usage data |
| Informed calm (during errors) | Error messages include: what happened, why, what to do next. Never just a status code. |
| Accomplishment | Quickstart flow with visible success state, usage graphs that show growing adoption |

### Emotional Design Principles

1. **Professional, not playful** — Developer tools earn trust through clarity and restraint, not personality. No mascots, no clever copy, no emoji in the UI. Let the product's utility speak.

2. **Explicit over implicit** — Show numbers, not vague indicators. "847 / 1,000 requests used" not "Almost at limit." "SN1: 142ms avg latency" not "Fast." Developers trust data.

3. **Errors are conversations, not dead ends** — Every error state should answer three questions: What happened? Why? What should I do now? A well-handled error builds more trust than a smooth happy path.

4. **Stability signals reliability** — Consistent layout, predictable navigation, no UI surprises between visits. The dashboard should feel like infrastructure — solid, unchanging, dependable.

5. **Absence of friction is the highest form of delight** — For developer tools, the best UX is invisible UX. Don't add delight through animation or micro-interactions — add it by removing steps, pre-filling fields, and making the obvious path the right path.

## UX Pattern Analysis & Inspiration

### Inspiring Products Analysis

**OpenAI Platform (platform.openai.com)** — The direct mental model. Priya already uses this daily. Key patterns: simple API key table with create/copy/revoke, usage graphs with per-model breakdown and date ranges, quickstart snippets in multiple languages, model listing with capability descriptions. Weakness: onboarding has become bloated (org setup, billing before first key) and usage page shows too many dimensions at once.

**Stripe Dashboard** — Gold standard for developer-facing dashboards. Key patterns: left sidebar navigation with clear grouping, progressive disclosure via summary cards → detail drill-down, test/live mode toggle for environment separation, clean data tables with inline actions, error states with documentation links. Weakness: feature density appropriate for Stripe's breadth would overwhelm TaoGateway's simpler product scope.

**Vercel Dashboard** — The minimal reference. Key patterns: visual restraint with whitespace and monospace fonts, deploy-first onboarding (success before configuration), simple green/yellow/red status dots, fast page loads and instant transitions. Weakness: sometimes too minimal — important information can be hard to discover.

### Transferable UX Patterns

**Navigation Patterns:**
- **Stripe's left sidebar with grouped sections** — Adopt for dashboard navigation. Groups: Overview, API Keys, Usage, Settings. Simple enough for MVP, extensible as features grow.
- **Stripe's test/live mode toggle** — Adapt for TaoGateway's `tao_sk_live_` / `tao_sk_test_` key prefix model. Visual environment indicator prevents production mistakes.

**Interaction Patterns:**
- **OpenAI's API key table** — Adopt directly. Create button, masked keys, copy-to-clipboard, revoke action. Developers expect exactly this layout.
- **Vercel's deploy-first onboarding** — Adapt as "key-first onboarding." Generate a key immediately after signup, show quickstart with key pre-filled, defer all other configuration.
- **OpenAI's code snippet tabs** — Adopt for quickstart. Tab between curl / Python / TypeScript with copy buttons. Auto-populate with the developer's real API key.

**Data Visualization Patterns:**
- **Stripe's summary cards → detail drill-down** — Adopt for usage monitoring. Overview shows total requests, top-line latency, quota status per subnet as cards. Click any card to see detailed graphs.
- **Vercel's status dots** — Adopt for subnet health. Green (available), yellow (degraded), red (down) next to each capability name. Simple, scannable, no cognitive load.
- **OpenAI's usage graphs with date range selector** — Adopt for usage page. Daily granularity, per-subnet breakdown, 90-day history. Recharts implementation.

**Information Architecture Patterns:**
- **Stripe's breadcrumbs** — Adopt for drill-down views. Usage Overview → Text Generation → Daily Detail. Always clear where you are and how to get back.
- **Progressive disclosure (all three)** — Core pattern: show the simplest useful view first, let users drill into detail. Never front-load complexity.

### Anti-Patterns to Avoid

1. **OpenAI's pre-key gatekeeping** — Requiring organization setup, billing configuration, or email verification before generating the first API key. TaoGateway must get a key into the developer's hands within 60 seconds of signup.

2. **Crypto dashboard aesthetics** — Dark themes with neon accents, animated charts, token price tickers, wallet connect buttons. These signal "DeFi app" not "developer tool." TaoGateway must look like Stripe, not like Uniswap.

3. **Jargon-first information architecture** — Organizing the dashboard around Bittensor concepts (subnets, metagraph, miners) instead of developer tasks (make requests, check usage, manage keys). The IA must be task-oriented, not domain-oriented.

4. **Dashboard-as-marketing** — Splash screens, feature announcements, upgrade prompts on every page. Developers visit the dashboard to do a job, not to be marketed to. Keep it utilitarian.

5. **Over-designed empty states** — Clever illustrations and witty copy for empty tables. For a developer tool, empty state should simply say what to do next: "No API keys yet. Create one to get started." with a create button.

6. **Modal overload** — Confirmation modals for non-destructive actions. Only use modals for irreversible operations (key revocation). Key creation, copying, and navigation should be modeless.

### Design Inspiration Strategy

**Adopt directly:**
- OpenAI's API key management table layout
- Stripe's left sidebar navigation structure
- Vercel's status dot indicators for health
- OpenAI's tabbed code snippets with copy buttons
- Stripe's summary card → detail drill-down pattern

**Adapt for TaoGateway:**
- Stripe's test/live toggle → environment indicator for key prefix types
- Vercel's deploy-first onboarding → key-first onboarding with pre-filled quickstart
- OpenAI's usage graphs → simplified for three subnets, framed as capabilities not models
- Stripe's data tables → lighter weight, fewer columns, appropriate for MVP data volume

**Avoid entirely:**
- Crypto/DeFi visual language (dark neon themes, token tickers, wallet connections)
- Pre-key gatekeeping (billing/org setup before first key)
- Domain-oriented IA (subnets/metagraph as navigation concepts)
- Marketing-heavy dashboard patterns (upgrade prompts, feature announcements)
- Over-designed empty states and error pages

## Design System Foundation

### Design System Choice

**shadcn/ui** — A collection of copy-paste React components built on Radix UI primitives and styled with Tailwind CSS. Components are copied into the project source, not installed as a dependency. Full code ownership with no external library to manage.

### Rationale for Selection

1. **Architecture alignment** — Tailwind CSS is already the locked-in styling solution per the architecture document. shadcn/ui is built natively for Tailwind — zero friction, zero adapter layers.

2. **Solo developer velocity** — Cevin is building this alone. shadcn/ui provides production-quality, accessible components (tables, cards, dialogs, tabs, forms, charts) out of the box. Building these from scratch with raw Tailwind would add weeks.

3. **Target aesthetic match** — shadcn/ui's default visual language is the exact Stripe/Vercel-style professional minimalism we identified as the design target. Clean typography, restrained color use, generous whitespace. Minimal customization needed to hit the right tone.

4. **Accessibility built-in** — Radix UI primitives handle keyboard navigation, focus management, ARIA attributes, and screen reader support. Critical for a professional developer tool, easy to overlook when building from scratch.

5. **Zero dependency risk** — Components are copied into the project, not imported from a package. No breaking changes from library updates, no version conflicts, no abandoned dependency risk. The code is yours.

6. **Recharts integration** — shadcn/ui includes chart components built on Recharts, which is already specified in the architecture document for usage visualization. Consistent styling between charts and UI components.

### Implementation Approach

**Setup:**
- Initialize shadcn/ui in the `dashboard/` directory with the default configuration
- Select Tailwind CSS as the styling engine (default)
- Use the "default" theme as the starting point (neutral, professional)

**Component adoption strategy:**
- Add components as needed, not all at once. Start with: Button, Card, Table, Dialog, Tabs, Input, Label, Badge, DropdownMenu
- Chart components added when implementing usage visualization
- Each component lives in `dashboard/src/components/ui/` — standard shadcn/ui convention

**Theme configuration:**
- Override CSS variables in `globals.css` for brand colors (defined in next steps)
- Keep the default font stack (Inter / system fonts) — professional, readable, fast-loading
- Maintain shadcn/ui's default spacing and sizing scale — consistent with Tailwind's design tokens

### Customization Strategy

**What to customize:**
- Brand colors (primary, accent) via CSS variables — applied globally, affects all components
- Status colors for subnet health indicators (green/yellow/red semantic colors)
- Code block styling for quickstart snippets (monospace font, syntax highlighting)

**What to keep as-is:**
- Component structure and accessibility behavior (Radix primitives)
- Default spacing, border radius, and shadow scales
- Typography scale and line heights
- Dark mode support (shadcn/ui includes it — enable but don't prioritize for MVP)

**What to extend:**
- Custom `SubnetStatusBadge` component combining Badge + status dot pattern
- Custom `ApiKeyRow` component combining Table row + copy button + masked key display
- Custom `QuotaBar` component for per-subnet quota visualization
- Custom `CodeSnippet` component with language tabs + copy button + key auto-fill

## Defining Experience

### The Core Interaction

**"Get an API key and make your first Bittensor-powered request in under 5 minutes — no wallet, no SDK, just HTTP."**

This is the interaction developers will describe to their friends. Not the dashboard, not the usage graphs — the moment a developer runs a curl command with their new key and gets an AI response back from a decentralized network they didn't have to understand.

### User Mental Model

Developers bring a specific mental model from OpenAI/Anthropic/Stripe:
1. Sign up with email
2. See a dashboard
3. Create an API key
4. Copy a quickstart snippet
5. Run it — it works
6. Integrate into their app

They expect this to take 5 minutes or less. Any deviation — extra steps, unfamiliar terms, required configuration — triggers "this isn't ready" and they leave.

**Priya's mental model:** "OpenAI but decentralized." She expects the same flow, the same response format, the same dashboard patterns. The only difference should be the base URL.

**Kai's mental model:** "Bittensor SDK but as HTTP calls." He understands what's happening under the hood and expects the gateway to abstract the Dendrite/Synapse/metagraph complexity into clean REST endpoints.

**Where existing solutions fail:** The Bittensor SDK requires Python installation, wallet creation and funding, hotkey registration, metagraph understanding, and async Dendrite code. This takes hours to days, not minutes. No alternative gateway exists — that's the opportunity.

### Success Criteria

| Criterion | Target | Failure Threshold |
|-----------|--------|-------------------|
| Time from signup to working API response | < 5 minutes | > 10 minutes |
| Steps between signup and key creation | 0 (immediate) | Any gatekeeping step |
| Quickstart snippet editing required | None (key pre-filled) | Manual key insertion |
| First request response time | 1-3 seconds | > 10 seconds |
| First request success rate | > 95% | < 80% |
| Bittensor-specific terms encountered during onboarding | 0 | Any term Priya would need to Google |

### Pattern Analysis

**Entirely established patterns.** Every step in the TaoGateway onboarding flow uses proven patterns that developers already know from OpenAI, Stripe, and Vercel. No novel interaction design needed. No user education required.

The innovation is not in the UX — it's in what the API provides access to. The UX should be invisible. The value is in the response that comes back from a decentralized AI network through a flow the developer already knows by heart.

**Familiar patterns adopted:**
- Email/password signup form (every SaaS)
- API key table with create/copy/revoke (OpenAI, Stripe, Anthropic)
- Tabbed code snippets with copy buttons (OpenAI, Vercel)
- Left sidebar dashboard navigation (Stripe, Vercel)
- Usage graphs with date range selectors (OpenAI, Stripe)

### Experience Mechanics

**The Onboarding Flow (step-by-step):**

**1. Signup (30 seconds)**
- Developer lands on signup page
- Email + password form. Cloudflare Turnstile for bot prevention (invisible in most cases — no checkbox, no puzzle).
- "Create account" button
- Account created, redirected to dashboard

**2. First Dashboard View (immediate)**
- Dashboard loads with empty state
- Prominent "Create your first API key" call-to-action
- No other distractions — no tour, no modal, no feature announcements

**3. Key Creation (10 seconds)**
- Click "Create API key"
- Key displayed in a modal: `tao_sk_live_abc123...`
- "Copy" button (copies to clipboard with visual confirmation)
- Warning: "This key won't be shown again. Copy it now."
- Close modal → key appears masked in the API Keys table

**4. Quickstart (30 seconds)**
- Quickstart panel appears after key creation (or modal transitions to it)
- Tabbed code snippets: **curl** | **Python** | **TypeScript**
- Developer's actual key pre-filled in every snippet
- Copy button per snippet
- curl example:
  ```
  curl -X POST https://api.taogateway.com/v1/chat/completions \
    -H "Authorization: Bearer tao_sk_live_abc123..." \
    -H "Content-Type: application/json" \
    -d '{"model":"tao-text","messages":[{"role":"user","content":"Hello"}]}'
  ```

**5. First Request (1-3 seconds)**
- Developer pastes into terminal, hits enter
- Response comes back: OpenAI-compatible JSON with AI-generated text
- Dashboard usage counter increments to 1

**6. Completion — "It works" moment**
- Developer is now a converted user
- Dashboard shows 1 request made, quota visible
- Path forward is clear: integrate into their app, explore other subnets
- Available capabilities (Text, Image, Code) visible in sidebar or overview

**What makes this fail (critical risks):**
- Email verification required before key creation — breaks the flow
- Organization or billing setup before key creation — unnecessary gatekeeping
- Quickstart requires manual key insertion — friction that causes errors
- First request fails with an unclear error — trust destroyed
- Response takes >10 seconds — feels broken
- Dashboard shows Bittensor jargon (metagraph, subnet, dendrite) — confusion

## Visual Design Foundation

### Color System

**Palette approach:** shadcn/ui default "zinc" neutral base with indigo primary accent. Minimal customization — leverage the design system's proven defaults.

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| **Primary** | Indigo | `#4F46E5` | Buttons, links, active states, focus rings, selected items |
| **Primary hover** | Indigo dark | `#4338CA` | Button hover, link hover |
| **Background** | White | `#FFFFFF` | Page background, main content area |
| **Surface** | Near-white | `#FAFAFA` | Sidebar background, card backgrounds, table header rows |
| **Elevated surface** | Light gray | `#F4F4F5` | Hover states on table rows, secondary cards |
| **Border** | Zinc | `#E4E4E7` | Card borders, table dividers, input borders |
| **Text primary** | Near-black | `#18181B` | Headings, body text, key labels |
| **Text secondary** | Gray | `#71717A` | Descriptions, metadata, timestamps, masked key suffixes |
| **Text muted** | Light gray | `#A1A1AA` | Placeholder text, disabled states |
| **Success** | Green | `#22C55E` | Subnet healthy, request succeeded, key active status dot |
| **Warning** | Amber | `#F59E0B` | Subnet degraded, approaching quota limit (>80%), sync stale |
| **Error** | Red | `#EF4444` | Subnet down, request failed, key revoked, destructive actions |
| **Code background** | Slate | `#1E293B` | Code snippet blocks, terminal-style displays |
| **Code text** | Light gray | `#E2E8F0` | Code text on dark background |

**Semantic color mappings (CSS variables):**
- `--primary`: Indigo — all interactive elements
- `--destructive`: Red — revoke key, delete account
- `--success`: Green — health indicators, positive states
- `--warning`: Amber — degraded states, quota warnings
- `--muted`: Gray — secondary information

**Dark mode:** shadcn/ui includes dark mode support via CSS variables. Enable the infrastructure (class-based toggling) but don't prioritize polish for MVP. Light mode is the default and primary experience.

### Typography System

**Font stack:**

| Role | Font | Fallback | Usage |
|------|------|----------|-------|
| **UI / Body** | Inter | `system-ui, -apple-system, sans-serif` | All dashboard text — navigation, labels, descriptions, headings |
| **Code / Monospace** | JetBrains Mono | `ui-monospace, 'Cascadia Code', 'Fira Code', monospace` | API keys, code snippets, endpoint URLs, response examples, request metadata |

**Type scale (Tailwind defaults):**

| Element | Size | Weight | Line Height | Usage |
|---------|------|--------|-------------|-------|
| Page title | 30px (`text-3xl`) | 600 (semibold) | 1.2 | Page headings: "API Keys", "Usage", "Overview" |
| Section heading | 20px (`text-xl`) | 600 (semibold) | 1.3 | Card titles, section labels |
| Body | 14px (`text-sm`) | 400 (normal) | 1.5 | Default text, table cells, descriptions |
| Small / Meta | 12px (`text-xs`) | 400 (normal) | 1.5 | Timestamps, helper text, badge labels |
| Code inline | 13px | 400 (normal) | 1.5 | Inline code references, API key prefixes |
| Code block | 14px | 400 (normal) | 1.6 | Quickstart snippets, response examples |

**Typography principles:**
- Inter for everything except code. No font switching between headings and body.
- Monospace for anything a developer would copy, type, or recognize as code.
- 14px base (not 16px) — developer dashboards are information-dense; slightly smaller text fits more content without feeling cramped.

### Spacing & Layout Foundation

**Base unit:** 4px (Tailwind default). All spacing as multiples of 4.

**Spacing scale (commonly used):**

| Token | Value | Usage |
|-------|-------|-------|
| `space-1` | 4px | Tight gaps: icon-to-label, badge padding |
| `space-2` | 8px | Default element gap: between form fields, list items |
| `space-3` | 12px | Table cell vertical padding, compact card padding |
| `space-4` | 16px | Table cell horizontal padding, input padding |
| `space-6` | 24px | Card padding, section gaps |
| `space-8` | 32px | Between major sections on a page |
| `space-12` | 48px | Page top/bottom margins |

**Layout structure:**

```
┌─────────────────────────────────────────────────────┐
│  Sidebar (240px fixed)  │  Main Content Area         │
│                         │                            │
│  Logo                   │  Page Header (title + actions) │
│  ─────────              │  ─────────────────────────  │
│  Overview               │                            │
│  API Keys               │  Content (max-width: 1200px│
│  Usage                  │  centered)                 │
│  ─────────              │                            │
│  Settings               │                            │
│  ─────────              │                            │
│  Docs ↗                │                            │
│                         │                            │
│  [avatar] Cevin     ▾  │                            │
└─────────────────────────────────────────────────────┘
```

- **Sidebar:** 240px fixed width. `#FAFAFA` background. Collapses to 64px icon-only on viewports below 1024px.
- **Main content:** Scrollable. Content max-width 1200px, centered with auto margins. Prevents excessively wide lines on ultrawide monitors.
- **Page header:** Sticky or fixed at top of main content. Contains page title and primary action button (e.g., "Create API Key" on the API Keys page).
- **Cards:** 24px padding, `#FFFFFF` background, 1px `#E4E4E7` border, 4px border-radius (shadcn/ui default).
- **Tables:** Full-width within cards. 12px vertical / 16px horizontal cell padding. Alternating row backgrounds not needed (clean borders are sufficient).

**Responsive behavior:**
- **≥1280px:** Full sidebar + full content area
- **1024-1279px:** Collapsed sidebar (icons only) + full content
- **<1024px:** Sidebar hidden behind hamburger menu + full-width content. Functional but not optimized — MVP is desktop-first.

### Accessibility Considerations

**Color contrast:** All text/background combinations meet WCAG 2.1 AA minimum (4.5:1 for body text, 3:1 for large text and UI components). The proposed palette achieves this — `#18181B` on `#FFFFFF` = 17.1:1, `#71717A` on `#FFFFFF` = 4.9:1.

**Color independence:** Status indicators (success/warning/error) never rely on color alone. Subnet health uses color dot + text label ("Healthy" / "Degraded" / "Down"). Quota warnings use color + explicit numbers ("847 / 1,000").

**Focus management:** shadcn/ui's Radix primitives handle focus rings, keyboard navigation, and ARIA attributes. No additional work needed for core accessibility.

**Font sizing:** 14px base is accessible at standard screen resolutions. Browser zoom support inherited from Tailwind's relative units.

**Motion:** No animations required for MVP. If added later, respect `prefers-reduced-motion` media query.

## Design Direction Decision

### Design Directions Explored

A unified design direction was explored through 8 interactive mockup views, each demonstrating how the visual foundation (indigo primary, zinc neutrals, Inter/JetBrains Mono typography, 240px sidebar layout) applies to real dashboard scenarios:

1. **Overview Dashboard** — Metric summary cards (balance, requests, active keys) with usage area chart and subnet health grid
2. **Onboarding Flow** — Guided first-time experience: create key → copy snippet → make request, with progress stepper
3. **API Keys Management** — Data table with masked keys, status badges, timestamps, and row-level actions
4. **Quickstart Panel** — Tabbed code snippets (curl/Python/TypeScript) with key auto-fill and copy-to-clipboard
5. **Usage Analytics** — Time-series charts with subnet breakdown and date range filtering
6. **Subnet Health** — Status cards with response time, reliability percentage, and color-coded status dots
7. **Empty States** — Minimal, actionable empty states directing users to their next step
8. **Key Creation Modal** — Focused dialog for key naming with immediate display and copy workflow

All views shared a consistent visual language: clean card layouts, generous whitespace, indigo interactive elements against white/zinc surfaces, monospace treatment for anything copy-worthy.

### Chosen Direction

**Single unified direction — accepted as presented.** The mockups demonstrated one cohesive visual system rather than competing directions, because the design constraints (shadcn/ui components, Stripe/Vercel-inspired patterns, indigo + zinc palette) naturally converge on a single professional developer-tool aesthetic.

Key elements confirmed:
- **Fixed sidebar navigation** with grouped sections (Overview, API Keys, Usage | Settings | Docs)
- **Card-based content organization** with consistent 24px padding and 1px zinc borders
- **Summary → detail drill-down** pattern for metrics and usage data
- **Inline actions** on table rows (copy, revoke) rather than navigation to detail pages
- **Dark code blocks** (`#1E293B`) for terminal-like snippet presentation
- **Status dot + text** pattern for subnet health indicators
- **Stepper-based onboarding** that tracks progress toward first successful API call

### Design Rationale

1. **Developer familiarity** — Every element maps directly to patterns developers encounter in OpenAI, Stripe, and Vercel dashboards. Zero learning curve, zero surprise.

2. **Information density match** — The 14px base text, compact table spacing, and card-based layout provide enough density for a developer tool without feeling cluttered. Right balance between "data-rich" and "approachable."

3. **Onboarding-centric hierarchy** — The design prioritizes the signup → key → quickstart → first request flow above all else. Empty states drive action, not explanation.

4. **Subnet abstraction** — Bittensor infrastructure is presented as capabilities with their subnet reference: Text Generation (SN1), Image Generation (SN19), Coding (SN62). Health indicators show status per subnet. Priya sees features with a parenthetical she can ignore; Kai sees the subnet he cares about.

5. **Consistent visual weight** — Indigo used sparingly for interactive elements and primary actions. No competing accent colors. Professional restraint that signals reliability.

### Implementation Approach

**Component build order (aligned with onboarding flow priority):**

1. **Shell first** — Sidebar navigation + page layout wrapper using shadcn/ui's Sheet and NavigationMenu components
2. **API Keys page** — Table, Badge, Button, Dialog components. This is the most-visited page.
3. **Key creation modal** — Dialog + Input + Button. The critical conversion moment.
4. **Quickstart panel** — Custom CodeSnippet component with Tabs. Appears post-key-creation.
5. **Overview dashboard** — Card + summary metrics. Uses Recharts for the usage area chart.
6. **Usage page** — Full Recharts implementation with date range selector (Select component).
7. **Subnet health** — Card grid with StatusBadge custom component.
8. **Empty states** — Variant of each page showing the zero-data experience.

**Shared components to create early:**
- `SubnetStatusBadge` — Badge + colored dot + text label
- `ApiKeyDisplay` — Monospace masked key with copy button
- `CodeSnippet` — Tabs + dark code block + copy button + key auto-fill
- `MetricCard` — Card with label, value, and optional trend indicator

**Design token setup:**
- Override shadcn/ui CSS variables in `globals.css` for brand colors on day one
- Configure Inter (Google Fonts or self-hosted) and JetBrains Mono
- All other shadcn/ui defaults (spacing, border-radius, shadows) kept as-is

## User Journey Flows

### Journey 1: First-Time Onboarding (Priya / Kai)

The critical conversion flow. Every decision optimizes for time-to-first-successful-request.

```mermaid
flowchart TD
    A[Landing Page / GitHub README] -->|Click signup link| B[Signup Page]
    B --> C{Cloudflare Turnstile}
    C -->|Pass - invisible| D[Create Account]
    C -->|Challenge| C1[Solve challenge]
    C1 --> D
    D --> E[Dashboard - Empty State]
    E --> F[CTA: Create Your First API Key]
    F --> G[Key Creation Modal]
    G --> H[Key Name Input - optional]
    H --> I[Key Generated + Displayed]
    I --> J{User copies key?}
    J -->|Yes - click Copy| K[Clipboard confirmed ✓]
    J -->|Closes without copying| L[Warning: key won't be shown again]
    L --> J
    K --> M[Modal transitions to Quickstart]
    M --> N[Tabbed snippets: curl / Python / TypeScript]
    N --> O[Key pre-filled in snippet]
    O --> P{User runs request}
    P -->|Success 200| Q[Dashboard updates: 1 request]
    P -->|Error| R[Error response with actionable message]
    R --> S[User adjusts and retries]
    S --> P
    Q --> T[Onboarding complete ✓]
    T --> U[Full dashboard available]
```

**Entry points:** Direct URL, GitHub README link, Hacker News/Discord mention
**Target time:** < 5 minutes from landing to successful API response
**Critical moment:** Key display modal — if they close without copying, the key is lost forever
**Failure recovery:** Clear error messages with specific fix instructions (wrong endpoint, malformed JSON, invalid key format)

**Priya vs Kai divergence:**
- Priya reads the quickstart literally, copies curl, runs it. Done.
- Kai skims quickstart, opens his IDE, replaces his Dendrite code with HTTP calls. Uses `/v1/models` to discover available subnets.

### Journey 2: API Key Lifecycle Management

Covers creation, usage, rotation, and revocation across a developer's lifetime with the platform.

```mermaid
flowchart TD
    A[API Keys Page] --> B{Has keys?}
    B -->|No| C[Empty State: Create your first key]
    B -->|Yes| D[Key Table View]

    D --> E[Create New Key]
    E --> F[Key Creation Modal]
    F --> G[Name input + Generate]
    G --> H[Display new key - copy now]
    H --> I[Key added to table - masked]

    D --> J[Copy Key Prefix]
    J --> K[Clipboard: tao_sk_live_abc...]

    D --> L[Revoke Key]
    L --> M[Confirmation Modal]
    M --> N{Confirm revoke?}
    N -->|Yes| O[Key revoked - status: Revoked]
    N -->|No| D
    O --> P[Active integrations will fail]

    D --> Q[View Key Details]
    Q --> R[Last used, created date, request count]
```

**Key table columns:** Name | Key (masked) | Status | Created | Last Used | Actions
**Actions per row:** Copy prefix | Revoke
**Status badges:** Active (green dot) | Revoked (red dot)
**Constraints:** No key editing after creation. No key unmasking after initial display. Revocation is permanent.

### Journey 3: Usage Monitoring & Quota Awareness (Priya / Marco)

How developers understand their consumption and make upgrade decisions.

```mermaid
flowchart TD
    A[Overview Dashboard] --> B[Metric Cards]
    B --> C[Total Requests Today]
    B --> D[Balance / Quota Status]
    B --> E[Active Keys Count]

    C --> F[Click for detail]
    F --> G[Usage Page]

    G --> H[Date Range Selector]
    H --> I[7d / 30d / 90d]

    G --> J[Usage Chart - Area/Line]
    J --> K[Per-subnet breakdown]
    K --> K1[Text Generation SN1]
    K --> K2[Image Generation SN19]
    K --> K3[Coding SN62]

    G --> L[Usage Table]
    L --> M[Daily breakdown with per-subnet counts]

    D --> N{Approaching limit?}
    N -->|>80% used| O[Warning badge on Overview]
    O --> P[Banner: Approaching quota limit]
    P --> Q[Link to upgrade / add balance]
    N -->|Under 80%| R[Normal display]

    N -->|Limit reached| S[Hard stop: 429 responses]
    S --> T[Dashboard shows quota exceeded]
    T --> Q
```

**Quota visibility:** Always visible in sidebar or overview card — never hidden until it's too late
**Warning threshold:** 80% of quota triggers amber warning badge
**Upgrade path:** Single link from warning → add balance page (post-MVP: Stripe checkout)
**Data granularity:** Daily buckets, per-subnet breakdown, 90-day retention

### Journey 4: Subnet Health Monitoring (Kai / Cevin)

How users check whether the capabilities they depend on are working.

```mermaid
flowchart TD
    A[Sidebar: Subnet Health] --> B[Health Page]
    B --> C[Subnet Cards Grid]

    C --> D[Text Generation SN1]
    C --> E[Image Generation SN19]
    C --> F[Coding SN62]

    D --> G{Status Check}
    E --> G
    F --> G

    G -->|Healthy| H[Green dot + Healthy]
    G -->|Degraded| I[Amber dot + Degraded]
    G -->|Down| J[Red dot + Down]

    H --> K[Response Time: ~1.2s]
    I --> L[Response Time: ~4.5s]
    I --> L1[Note: Reduced miner availability]
    J --> M[Response Time: --]
    J --> M1[Note: All miners unavailable]

    B --> N[Overview also shows health grid]
    N --> O[Mini status dots per subnet]
    O --> P[Click → Health page for detail]
```

**Health sources:** Derived from recent request success rates and response times (gateway internal metrics, not user-facing pings)
**Refresh:** Auto-refresh every 60 seconds on health page, manual refresh button available
**Kai's use case:** Check health before routing multi-subnet pipeline requests
**Cevin's use case:** Morning check, incident response when Discord reports issues

### Journey Patterns

**Pattern: Progressive Disclosure**
Every page follows: summary view → click for detail. Overview cards → Usage page. Health dots → Health page. Key table → key details. Users never need to process all information at once.

**Pattern: Action-Oriented Empty States**
Every empty state has exactly one CTA pointing to the next logical action. No illustrations, no clever copy. "No API keys yet. Create one to get started." + button.

**Pattern: Inline Feedback**
Success/failure feedback appears in context — clipboard confirmation next to the copy button, status changes in the table row, quota warnings in the metric card. No toast notifications except for destructive actions (key revocation).

**Pattern: Confirmation Only for Destructive Actions**
Key creation: no confirmation (instant). Copying: no confirmation (instant + visual feedback). Key revocation: confirmation modal required ("This will immediately invalidate this key. Active integrations using this key will stop working.").

**Pattern: Consistent Navigation**
Sidebar is always visible. Current page highlighted. No breadcrumbs needed at MVP depth (max 2 levels). Page title in the main content area matches the sidebar label exactly.

### Flow Optimization Principles

1. **Zero-step onboarding** — Account creation leads directly to the dashboard. No email verification, no profile setup, no tour modal. The dashboard itself is the onboarding.

2. **Clipboard as the critical handoff** — The API key copy and quickstart snippet copy are the two moments where value transfers from the dashboard to the developer's workflow. These must be bulletproof: large click targets, instant visual confirmation, no ambiguity.

3. **Quota as a feature, not a wall** — Quota visibility is always present (not just at limit). Developers should be able to plan around their quota, not be surprised by it. Warning at 80%, not at 100%.

4. **Health transparency builds trust** — Showing subnet health openly (including degraded/down states) builds more trust than hiding problems. Developers who can see the system is being honest about its state will tolerate occasional degradation.

5. **Error messages as documentation** — Every error response the API returns should be informative enough that the developer doesn't need to open the docs. Include: what went wrong, why, and what to do about it.

## Component Strategy

### Design System Components (shadcn/ui)

| Component | Used In | Notes |
|-----------|---------|-------|
| **Button** | Every page | Primary (indigo), secondary (outline), destructive (red for revoke) |
| **Card** | Overview, Health, Usage | Metric cards, subnet cards, content containers |
| **Table** | API Keys, Usage | Key list, daily usage breakdown |
| **Dialog** | Key creation, key revocation | Modal flows for focused actions |
| **Input** | Key creation, signup | Text fields with labels |
| **Label** | Forms | Paired with inputs |
| **Badge** | Key status, subnet status | Active/Revoked, Healthy/Degraded/Down |
| **Tabs** | Quickstart snippets | curl / Python / TypeScript switching |
| **DropdownMenu** | User menu, key actions | Sidebar user menu, row-level actions |
| **Select** | Usage page | Date range selector (7d/30d/90d) |
| **Tooltip** | Various | Hover explanations for truncated data |
| **Sheet** | Mobile sidebar | Responsive sidebar drawer |
| **Separator** | Sidebar | Section dividers in navigation |

**Charts (shadcn/ui + Recharts):**
- **AreaChart** — Usage over time on Overview and Usage pages
- **BarChart** — Per-subnet usage breakdown (if needed)

### Custom Components

#### SubnetStatusBadge

**Purpose:** Display subnet health status with color-coded dot and text label.
**Anatomy:** `[● dot] [status text] [subnet label]`
**States:**
- Healthy: green dot + "Healthy" text
- Degraded: amber dot + "Degraded" text
- Down: red dot + "Down" text

**Built from:** shadcn Badge + custom dot element
**Usage:** Health page cards, Overview health grid, any subnet reference

#### ApiKeyDisplay

**Purpose:** Show a masked API key with one-click copy.
**Anatomy:** `[tao_sk_live_abc1...] [Copy icon button]`
**States:**
- Default: masked key in monospace
- Copied: checkmark icon + "Copied" text (2s, then revert)
- Full display (creation modal only): full key shown, never again after modal closes

**Built from:** monospace `<code>` + shadcn Button (icon variant) + clipboard API
**Usage:** API Keys table rows, Key creation modal

#### CodeSnippet

**Purpose:** Display pre-filled code examples with language tabs and copy functionality.
**Anatomy:** `[Tab bar: curl | Python | TypeScript] [Dark code block] [Copy button]`
**States:**
- Default: curl tab active, user's API key pre-filled
- Tab switched: content changes, key remains filled
- Copied: button shows "Copied ✓" (2s, then revert)

**Built from:** shadcn Tabs + custom dark-background `<pre>` block + copy button
**Usage:** Quickstart panel (post-key-creation), docs integration

#### MetricCard

**Purpose:** Display a single key metric with label, value, and optional context.
**Anatomy:** `[Label] [Value — large text] [Subtitle or trend]`
**States:**
- Normal: neutral styling
- Warning: amber border or accent when quota > 80%
- Clickable: hover state when card links to detail page

**Built from:** shadcn Card with custom internal layout
**Usage:** Overview dashboard (Balance, Requests Today, Active Keys)

#### QuotaBar

**Purpose:** Visualize per-subnet quota usage as a progress bar.
**Anatomy:** `[Subnet label (SN1)] [Progress bar] [847 / 1,000]`
**States:**
- Normal (< 80%): indigo fill
- Warning (80-99%): amber fill
- Exceeded (100%): red fill + "Quota exceeded" text

**Built from:** HTML progress/div + Tailwind styling
**Usage:** Overview card, Usage page, sidebar widget (optional)

#### OnboardingStepper

**Purpose:** Guide first-time users through the key creation → quickstart → first request flow.
**Anatomy:** `[Step 1: Create Key ●] — [Step 2: Copy Snippet ○] — [Step 3: Make Request ○]`
**States:**
- Step complete: filled indigo dot + strikethrough text
- Step current: outlined indigo dot + bold text
- Step pending: gray dot + normal text

**Built from:** Custom flex layout + conditional styling
**Usage:** Onboarding empty state (dismissed after first successful request)

### Component Implementation Strategy

**Principles:**
- All custom components use shadcn/ui design tokens (colors, spacing, border-radius, shadows) — no ad-hoc styling
- Composition over complexity — custom components are thin wrappers around shadcn primitives, not independent component systems
- Each custom component lives in `dashboard/src/components/` (not in `ui/` — that's reserved for shadcn)
- No component library package — these are project components, not reusable across projects

**Testing approach:**
- Components are simple enough that page-level integration tests cover them
- No component-level unit tests unless logic is complex (QuotaBar threshold calculation)

### Implementation Roadmap

**Phase 1 — Onboarding Critical Path:**
1. App shell (sidebar + layout) using Sheet, NavigationMenu, Separator
2. ApiKeyDisplay + Dialog → Key creation modal
3. CodeSnippet + Tabs → Quickstart panel
4. OnboardingStepper → First-time dashboard experience
5. Button, Input, Label → Signup form

**Phase 2 — Dashboard Core:**
6. MetricCard + Card → Overview page
7. Table + Badge + ApiKeyDisplay → API Keys page
8. AreaChart (Recharts) → Usage overview chart
9. SubnetStatusBadge + Card → Health status grid

**Phase 3 — Detail Views:**
10. Select + AreaChart → Usage page with date range filtering
11. QuotaBar → Quota visualization
12. Table → Usage breakdown table

## UX Consistency Patterns

### Button Hierarchy

| Level | Style | Usage | Example |
|-------|-------|-------|---------|
| **Primary** | Solid indigo, white text | One per page section — the main action | "Create API Key", "Create Account" |
| **Secondary** | Outline, indigo border/text | Supporting actions alongside primary | "View Docs", "Export Usage" |
| **Ghost** | No border, text only | Inline/row-level actions, navigation links | "Copy", sidebar items |
| **Destructive** | Solid red, white text | Irreversible actions, always inside a confirmation dialog | "Revoke Key" |
| **Icon** | Square button, icon only | Compact actions in tight spaces | Copy icon, refresh icon |

**Rules:**
- Maximum one primary button visible per content section
- Destructive buttons never appear without a preceding confirmation step
- Icon buttons always have a Tooltip for accessibility
- Button loading state: spinner replaces icon/text, button disabled — no double-submit

### Feedback Patterns

**Success feedback:**
- Inline, contextual, temporary. Appears next to the trigger element.
- Copy actions: icon changes to checkmark + "Copied" for 2 seconds, then reverts
- Key creation: key displayed immediately in modal — no separate success screen
- No toast notifications for non-destructive success

**Error feedback:**
- API errors: displayed in the response body with status code, message, and remediation steps
- Form validation: inline below the field, red text, appears on blur or submit
- Page-level errors: banner at top of content area (red background, white text) with dismiss button
- Never use alerts/popups for errors — always inline

**Warning feedback:**
- Quota approaching: amber badge on MetricCard, persists until quota resets or user upgrades
- Destructive action confirmation: modal with explicit description of consequences
- Warning text is always specific: "847 of 1,000 requests used" not "Approaching limit"

**Loading states:**
- Page load: skeleton placeholders matching the content layout (shadcn Skeleton component)
- Data refresh: subtle spinner in the page header, content remains visible
- Button action: spinner replaces button content, button disabled
- Never block the entire page — always show the shell/sidebar while content loads

### Form Patterns

**Signup form (the only public form):**
- Two fields: email + password. No name, no organization, no phone.
- Validation on submit, not on keystroke. Field-level error messages.
- Single "Create Account" primary button
- Cloudflare Turnstile renders below the form (invisible in most cases)

**Key creation form (modal):**
- One optional field: key name (placeholder: "e.g., production, testing")
- If left blank, auto-generate name: "Key 1", "Key 2", etc.
- Single "Generate Key" primary button
- No cancel button — closing the dialog cancels

**General form rules:**
- Labels above inputs, not inline or floating
- Required fields are the default — don't mark them. Mark optional fields with "(optional)"
- Tab order follows visual order, top to bottom
- Submit on Enter for single-field forms

### Navigation Patterns

**Sidebar navigation:**
- Always visible on desktop (≥1024px)
- Grouped sections separated by Separator component:
  - Group 1: Overview, API Keys, Usage
  - Group 2: Health
  - Group 3: Settings
  - Group 4: Docs (external link, opens new tab, indicated by ↗ icon)
- Active page: indigo text + subtle indigo background on sidebar item
- Hover: light gray background
- User menu at bottom: avatar + name + dropdown (Settings, Sign Out)

**Page structure:**
- Every page has: page title (h1, top-left) + optional primary action button (top-right)
- No breadcrumbs at MVP depth (max 1 level deep)
- No tabs for top-level navigation — tabs reserved for content switching within a page (e.g., code snippets)

**External links:**
- Always open in new tab
- Always indicated with ↗ icon suffix
- Used for: Docs site, GitHub repo

### Data Display Patterns

**Tables:**
- Full-width within their Card container
- Column headers: uppercase, text-xs, text-muted, semibold
- Row hover: light gray background (`#F4F4F5`)
- No alternating row colors — clean borders sufficient
- Actions column: right-aligned, ghost buttons
- Empty table: single row spanning all columns with CTA text + button

**Metric values:**
- Numbers always formatted with commas: "1,247" not "1247"
- Currency: "$12.50" with two decimal places
- Percentages: "94.2%" with one decimal
- Timestamps: relative when recent ("2 hours ago"), absolute when old ("Mar 8, 2026")
- Response times: "1.2s" — always one decimal, always in seconds

**Status indicators:**
- Always: colored dot + text label. Never color alone.
- Green dot: "Healthy" / "Active"
- Amber dot: "Degraded" / "Warning"
- Red dot: "Down" / "Revoked" / "Error"
- Dot size: 8px, placed left of the text label

### Modal Patterns

**When to use modals:**
- Key creation (focused task, prevents accidental navigation away from displayed key)
- Key revocation confirmation (destructive action requiring explicit confirmation)
- Nothing else at MVP. No modals for navigation, settings, or information display.

**Modal behavior:**
- Backdrop click closes the modal (except during key display — must explicitly close)
- Escape key closes the modal
- Focus trapped within modal while open
- Primary action button right-aligned in modal footer
- Cancel is always available via close button (X) — no explicit "Cancel" button needed

### Clipboard Patterns

**Copy interactions (the most frequent action in the dashboard):**
- Click target: the entire copy button, not just the icon
- Feedback: icon changes from clipboard → checkmark, text shows "Copied" for 2 seconds
- Fallback: if clipboard API unavailable, select the text for manual copy
- What's copyable: API keys (full on creation, prefix after), code snippets, endpoint URLs
- Monospace treatment for all copyable text — visual signal that "this is something you'll paste somewhere"

## Responsive Design & Accessibility

### Responsive Strategy

**Desktop-first.** TaoGateway's dashboard is a developer tool used while coding — overwhelmingly on desktop. Mobile support is functional but not optimized.

**Desktop (≥1280px) — Primary experience:**
- Full 240px sidebar + scrollable main content (max-width 1200px)
- All features fully accessible, optimal information density
- Multi-column card layouts for Overview and Health pages

**Small desktop / tablet landscape (1024–1279px):**
- Sidebar collapses to 64px icon-only mode
- Hover tooltip on sidebar icons shows page names
- Main content expands to fill available width
- Card grids reduce from 3-column to 2-column

**Tablet portrait / mobile (<1024px):**
- Sidebar hidden, accessible via hamburger menu (Sheet component)
- Single-column card layout
- Tables become horizontally scrollable within their card container
- Code snippets remain full-width with horizontal scroll
- Touch targets minimum 44x44px for all interactive elements
- Functional but not the design target — developers rarely manage API keys from their phone

### Breakpoint Strategy

| Breakpoint | Tailwind class | Layout change |
|------------|---------------|---------------|
| `≥1280px` | `xl:` | Full sidebar + 3-column card grid |
| `≥1024px` | `lg:` | Collapsed sidebar (icons) + 2-column grid |
| `<1024px` | default | Hidden sidebar + single column |

**Implementation approach:**
- Tailwind responsive prefixes (`lg:`, `xl:`) — no custom media queries
- Desktop-first in practice: build the full layout, then add responsive overrides for smaller screens
- No separate mobile components — same components adapt via Tailwind classes

### Accessibility Strategy

**Target: WCAG 2.1 AA compliance.** This is the industry standard for developer tools and covers the legal and ethical baseline without the overhead of AAA.

**What we get for free from shadcn/ui + Radix:**
- Keyboard navigation for all interactive components (buttons, dialogs, dropdowns, tabs)
- Focus trapping in modals
- ARIA roles and labels on primitive components
- Focus ring visibility on keyboard navigation (hidden on mouse click)
- Escape key handling for overlays

**What we implement ourselves:**
- Semantic HTML structure (`<nav>`, `<main>`, `<header>`, `<table>`) — not div soup
- Skip link: hidden link at top of page, visible on focus, jumps to main content area
- `aria-label` on icon-only buttons (copy, refresh, external link)
- `aria-live` region for clipboard feedback ("Copied" announcements)
- Status dot color independence: always paired with text label ("Healthy", "Down")
- Form error association: `aria-describedby` linking inputs to their error messages

**Color contrast verification:**

| Combination | Ratio | Passes AA? |
|-------------|-------|------------|
| Primary text (#18181B) on white (#FFFFFF) | 17.1:1 | Yes |
| Secondary text (#71717A) on white (#FFFFFF) | 4.9:1 | Yes |
| Indigo (#4F46E5) on white (#FFFFFF) | 6.4:1 | Yes |
| Code text (#E2E8F0) on code bg (#1E293B) | 11.1:1 | Yes |
| White text on indigo button (#4F46E5) | 6.4:1 | Yes |
| White text on red destructive (#EF4444) | 4.6:1 | Yes (borderline) |

### Testing Strategy

**Responsive testing (MVP scope):**
- Chrome DevTools device simulation for breakpoint verification
- Manual check on one real mobile device (iPhone) for touch target sizing
- No dedicated tablet testing at MVP — breakpoint simulation sufficient

**Accessibility testing (MVP scope):**
- axe DevTools browser extension for automated WCAG scanning during development
- Manual keyboard-only navigation test: can every action be completed without a mouse?
- VoiceOver spot-check on macOS: verify key creation flow and clipboard feedback are announced
- No formal accessibility audit at MVP — automated tooling + manual spot checks

**Post-MVP:**
- Consider Lighthouse CI for automated accessibility regression in CI/CD
- Real-device testing across iOS Safari and Android Chrome if mobile usage grows

### Implementation Guidelines

**HTML structure:**
```html
<body>
  <a href="#main" class="skip-link">Skip to main content</a>
  <nav aria-label="Main navigation"><!-- sidebar --></nav>
  <main id="main">
    <header><!-- page title + actions --></header>
    <section><!-- page content --></section>
  </main>
</body>
```

**Responsive patterns:**
- Use Tailwind's `container` for max-width constraints
- Grid layouts: `grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3`
- Sidebar visibility: `hidden lg:flex` for collapsed, `hidden xl:flex` for full
- Tables: wrap in `overflow-x-auto` for horizontal scroll on small screens

**Accessibility patterns:**
- Every `<img>` has `alt` text (or `alt=""` for decorative images)
- Every form input has a visible `<label>` (no placeholder-as-label)
- Color is never the sole indicator — always paired with text or icon
- Focus order matches visual order — no `tabindex` hacks
- `prefers-reduced-motion`: respect for any future animations
