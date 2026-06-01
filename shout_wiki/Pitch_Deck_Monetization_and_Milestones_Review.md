# Pitch Deck Monetization and Milestones Review

This review evaluates Slide 7 (Monetization Paths) and Slide 9 (Milestones & Roadmap) of the pre-seed investor pitch deck outline against our Sprint 1 OKRs, business goals, and development timelines.

---

## 1. Slide 7: Monetization Paths (Business & Revenue Alignment)

Our revenue model must show investors a high-margin, scalable path without killing early user adoption.

### 1.1 Transaction Take Rate (Primary)
*   **Current Spec**: 1.5% convenience fee markup on Stripe card payments.
*   **Assessment**: We must be clear here. Stripe’s standard Australian rate is 1.75% + $0.30 AUD for domestic cards. If we only charge 1.5% total convenience fee, we are losing money on every transaction. 
*   **Alignment**: This fee must be a **1.5% markup on top of payment processing costs** (or a 1.5% net take rate for Shout). During split checkout, Kong must implement the calculation as: `Total Charge = Split Share + Stripe Base Fee + 1.5% Shout Markup`.
*   **Action**: Liam to update the pitch deck copy and PRD to clarify this as a "net take rate" to avoid investor queries about negative unit economics.

### 1.2 Express Payout Premium
*   **Current Spec**: 1.0% fee for instant balance cash-out (standard 2-3 day transfers are free).
*   **Assessment**: This is our cleanest early revenue stream. It addresses a major user pain point (waiting for cash) and has almost zero incremental processing cost.
*   **Alignment**: We must keep this front and center. Ensure this features prominently in our MVP demo.

### 1.3 B2B Venue Commissions
*   **Current Spec**: Revenue share from partner venues (e.g., Felons Brewing Co.) for QR-driven orders.
*   **Assessment**: Highly valuable for GTM, but POS (Point of Sale) integrations are notorious development bottlenecks. 
*   **Alignment**: We cannot commit to deep POS API integration for the June demo. Phase 1 must focus on simple manual entry or lightweight webhooks. We'll pitch POS integration as a Post-Funding milestone.

### 1.4 Shout Pro Subscription
*   **Current Spec**: $3.99 AUD/month for OCR receipt scanning, custom themes, premium stickers.
*   **Assessment**: Good for recurring revenue (LTV) storytelling, but highly complex. OCR engines are notoriously difficult to get right on mobile browsers.
*   **Alignment**: Shift the technical execution of the OCR engine entirely to Phase 4 (Q4). Under no circumstances is Kong to work on Pro tier features during Sprint 1 or 2.

---

## 2. Slide 9: Milestones & Roadmap (Development Alignment)

We have zero lines of functional code in the app directory, and our June investor demo is non-negotiable. Our milestone roadmap must reflect a realistic timeline, not fantasy.

### 2.1 June (Phase 1): Zero-Friction MVP
*   **Timeline**: Extremely tight (Sprints 1-3).
*   **Target**: Real-time chat, Plaid transaction sync, and Stripe checkout.
*   **Assessment**: This must be bulletproof. If the live demo crashes or drops WebSocket state in front of angel investors, we won't get a dollar. 
*   **Strategic Priority**: Defer all UI polish and animations to Sprint 3 or post-demo. Focus strictly on API endpoints and baseline Socket.io connections.

### 2.2 Q3 Start (Phase 2): Viral Referral Engine
*   **Timeline**: Extremely tight (Sprints 1-3).
*   **Target**: $5 AUD sign-up credits, social sharing.
*   **Assessment**: Realistic. We'll need the funding locked in first to subsidize the referral payouts.

### 2.3 Q3 Mid (Phase 3): Table QR Ordering & Venue Pilots
*   **Target**: POS api integrations, Felons pilot.
*   **Assessment**: Highly dependent on locking in our venue partnerships. We need to start talks with Felons early, but keep dev work isolated until the MVP is proven.

### 2.4 Q4 (Phase 4): Shout Pro & Premium Customization
*   **Target**: OCR Engine, custom styling, subscription billing.
*   **Assessment**: Keep this in Q4. It gives us a strong future monetization story for investors without distracting the current sprint.

---

## 3. Summary of Pitch Deck Changes Needed
1.  **Slide 7**: Change "1.5% convenience fee" to "1.5% net take rate markup" to protect margins.
2.  **Slide 7**: Highlight "Express Payout Premium (1.0%)" as our primary high-margin liquidity feature.
3.  **Slide 9**: Group the milestones into "Pre-Seed Scope" (June MVP) and "Post-Funding Milestones" (Q3-Q4) so investors see a logical progression of capital deployment.

---

[TASK_UPDATE: TASK-010 | status | done]
[TASK_UPDATE: TASK-010 | deliverable_ref | Drafted the Pitch Deck Monetization and Milestones Review in shout_wiki/Pitch-Deck-Monetization-and-Milestones-Review.md and updated the project Home page.]