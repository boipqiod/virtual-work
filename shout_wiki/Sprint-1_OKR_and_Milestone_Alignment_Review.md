# Sprint 1 OKR and Milestone Alignment Review

We are officially in motion with Sprint 1. The workspace scaffolding is locked in, but let's be realistic: we have zero lines of functional code in place, and the clock is ticking toward our June investor demo. With a $500,000 AUD pre-seed round on the line, we can't afford to waste time on low-priority tasks.

Here is the strategic alignment review of our current progress, risks, and roadmap priorities.

---

## 1. Sprint 1 OKRs & Demo Readiness

### OKR 1: Core Monorepo & Baseline Architecture
*   **Target**: Decoupled monorepo with Next.js frontend, Node Express backend, and unified dev scripts.
*   **Status**: **On Track**. Workspace scaffolding is complete (Issue #4 closed).
*   **Business Impact**: Establishes the workspace for Kong to write code without backend-frontend bleeding.

### OKR 2: Baseline Socket.io Integration
*   **Target**: Real-time communication between frontend and backend in local sandbox.
*   **Status**: **In Progress**.
*   **Business Impact**: Necessary foundation for the live chat split experience.

### OKR 3: Milestone Alignment (June Investor Demo)
*   **Target**: Working prototype showing real-time chat split (Plaid sync -> Stripe checkout -> live progress update).
*   **Status**: **At Risk**. While the spec documents are in great shape, we need to see working features in the app directory. Investors aren't funding markdown files; they want to see a flawless live demo.

---

## 2. Strategic Trade-offs & Priorities

### Core payment loops vs. Visual Polish
Chloe is pushing for custom themes and rich micro-animations. While a premium aesthetic is vital for our target Aussie demographic (especially launching around Fortitude Valley and West End), we have to ask: how does this move the needle on our MVP demo if the underlying Plaid transaction sync or Stripe payment flow fails? The priority is functional stability first. Chloe's UI styling rules will be applied once the core API integrations are proven.

### Deferring Socket Resilience
Aiden has drafted robust guidelines in [WebSocket-State-Reconciliation-and-Resilience-Guidelines.md](file:///Users/kong/Desktop/Develop/VirtualWork/virtual-work/shout_wiki/WebSocket-State-Reconciliation-and-Resilience-Guidelines.md). However, we've agreed to push the detailed recovery tickets (handling connection drops in basement venues) to Sprint 2. This keeps Kong focused on getting the baseline chat up this week.

### Plaid Webhook Spike
Plaid sync is our primary differentiator against Splitwise's manual entries. Aiden's spec [Plaid-Integration-and-Webhook-Sync-Spec.md](file:///Users/kong/Desktop/Develop/VirtualWork/virtual-work/shout_wiki/Plaid-Integration-and-Webhook-Sync-Spec.md) is solid, but Kong needs to run a tech spike on sandbox auth and webhook sync immediately. We can't have duplicate splits or connection drop crashes.

---

## 3. Financial Metrics & Growth Strategy

Our pre-seed round valuation is tied to demonstrating clear paths to our monetization model:
1.  **Stripe Convenience Rate**: 1.5% take rate on all splits. Kong must build this calculation directly into the split checkout view.
2.  **Express Payout Premium**: 1.0% fee for instant settlement. This is high-margin revenue that addresses a major user pain point.
3.  **Target CAC**: We are modeling a Customer Acquisition Cost of under $2.50 AUD, driven by the viral loop of users inviting friends to split bills at venues like Felons Brewing Co.
4.  **B2B Commission**: Revenue share with launch venues for QR-driven orders.

---

## 4. Immediate Action Items

*   **Kong**: Focus entirely on the Express backend base and baseline Socket.io chat room. Do not start on custom styling or OCR yet.
*   **Aiden**: Stand ready to review Kong's baseline PRs within 24 hours of submission. We need to catch any architectural bloat early.
*   **Liam**: Monitor the burn rate of tasks on the project board daily. We need to prevent scope creep from leaking into subsequent sprints.