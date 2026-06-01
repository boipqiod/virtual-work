# Shout Pre-Seed Investor Pitch Deck Outline

This outline defines the slide-by-slide structure, core narrative, and visual guidelines for Shout's upcoming **$500,000 AUD pre-seed funding round**.

---

## 🎨 Visual Identity & Aesthetic Guidelines (Marketing Notes)
*   **Color Palette**: Midnight obsidian background (sleek dark mode) paired with vibrant neon coral accents and electric violet gradients. No generic corporate greys.
*   **Typography**: Bold, punchy headers (Outfit or Space Grotesk) with highly readable sans-serif body text (Inter).
*   **Interface Mockups**: Show high-fidelity mobile-first app designs containing custom animated cards and smooth progress-bar micro-animations inside the chat room. 

---

## 🗂️ Slide-by-Slide Outline

### Slide 1: The Hook (Title Slide)
*   **Visual**: A stunning mock phone mockup showcasing a vibrant group chat with a "Shout Card" sliding in smoothly.
*   **Copy**: *Shout: Making bill splitting social, instant, and frictionless.*
*   **Key Message**: Peer-to-peer payments are boring utilities; Shout transforms them into a social experience.

### Slide 2: The Problem (Social Dining Friction)
*   **Visual**: Clean infographics showing the awkwardness of manual calculations at the end of a group night out at *Felons Brewing Co.* in Brisbane.
*   **Copy**: *Group dinners end in math homework, copy-pasting BSB numbers, and awkward follow-ups.*
*   **Key Data**:
    *   74% of Gen Z/Millennials find manual bill splitting stressful or annoying.
    *   Aussie banks require manual transfer details (BSB/Account No.), resulting in delayed settlements and forgotten debts.

### Slide 3: Competitor Gaps (Beem vs. Splitwise)
*   **Visual**: A comparative grid highlighting key limitations.
*   **Core Competitive Deep-Dive**:
    *   **Beem**: Useful P2P payment rail, but operates as a dry, text-only banking utility. Zero social connection, no transaction syncing, and no venue integration.
    *   **Splitwise**: Global leader in ledger tracking, but lacks integrated Aussie payment rails. Users must leave the app to pay manually. Aggressive banner ads and daily transaction limits on the free tier drive massive user frustration.
*   **Our Edge**: Shout bridges this gap by merging Splitwise's ledger logic with Beem's payment execution, entirely embedded inside a social-first chat stream.

### Slide 4: The Solution (Value Proposition)
*   **Visual**: Interactive walk-through of the Shout user interface.
*   **Copy**: *Real-time chat meets instant payment rails.*
*   **Core Value Props**:
    1.  **Chat-Embedded Splits**: Create a group chat room and split bills directly in the conversation.
    2.  **Plaid Transaction Syncing**: Connect a bank account securely and tap a past transaction to split—no manual data entry.
    3.  **Stripe Instant Payments**: Pay split shares immediately via debit/credit card inside the chat stream.

### Slide 5: The Technology (How It Works)
*   **Visual**: Simple 3-step technical workflow diagram (Client $\rightarrow$ WebSockets/Socket.io $\rightarrow$ Express Backend $\rightarrow$ Plaid/Stripe Sandboxes).
*   **Details**:
    *   **Real-time sync**: WebSockets ensure immediate state reconciliation and progress bar updates.
    *   **Security & resilience**: Offline recovery for WebSocket connection drops, state syncing via robust database ledgers.

### Slide 6: Market Opportunity (The Next-Gen Aussie Diner)
*   **Visual**: Map highlighting major Australian urban hubs, starting with Fortitude Valley and Teneriffe in Brisbane, expanding nationwide.
*   **Copy**: *Capturing the $12B AUD annual hospitality spend of young Australians.*
*   **Target CAC**: < $2.50 AUD driven by organic referral loops and table QR placements.

### Slide 7: Monetization Paths (How We Make Money)
*   **Visual**: Clear visual breakdown of Shout's four revenue streams, highlighting core margins and timeline phasing:
    1.  **Express Payout Premium (Primary High-Margin Liquidity Feature)**: 1.0% fee for instant balance cash-out to external bank accounts (standard 2-3 day transfers remain free). Direct path to early high-margin revenue with negligible processing costs.
    2.  **Transaction Take Rate**: 1.5% net take rate markup on top of payment processing costs (Stripe base fees of 1.75% + $0.30 AUD passed through to protect unit economics).
    3.  **B2B Venue Commissions (Post-Funding Scale)**: Revenue share/commission from partner venues (starting with *Felons Brewing Co.*) for orders driven through table QR codes. Phase 1 focuses on manual entry/lightweight webhooks; deep POS API integration is deferred to post-funding.
    4.  **Shout Pro Subscription (Post-Funding LTV)**: $3.99 AUD/month for power users. Advanced features like OCR receipt scanning, custom themes, and premium stickers. (Technical execution of the OCR engine shifted entirely to Q4/Phase 4).

### Slide 8: Viral Growth Loops & GTM Strategy
*   **Visual**: Diagram showing the referral engine loop.
*   **Copy**: *Built-in virality. Every split invites new active users.*
*   **Core Tactics**:
    *   **Referral Loop**: $5 AUD sign-up and split credit for both referrers and new active users.
    *   **Table QR Codes**: Direct room creation and split generation at partner dining venues.
    *   **Social Share Loop**: One-click sharing of dining summaries to Instagram/TikTok stories.

### Slide 9: Milestones & Roadmap
*   **Visual**: Timeline dividing pre-seed delivery from post-funding scaling to demonstrate disciplined capital deployment.
*   **Pre-Seed Scope (June MVP / Phase 1)**:
    *   **June (Phase 1) - Zero-Friction MVP**: Focused on core utility—real-time chat, Plaid transaction sync, and Stripe checkout. Highly reliable API endpoints and baseline Socket.io connections; UI polish and micro-animations deferred to Sprint 3 or post-demo to ensure absolute stability.
*   **Post-Funding Milestones (Q3 - Q4 Scaling)**:
    *   **Q3 Start (Phase 2) - Viral Referral Engine**: Launch $5 AUD sign-up/split credit and social share loops, funded and scaled by the capital injection.
    *   **Q3 Mid (Phase 3) - Table QR Ordering & Venue Pilots**: Deploy table QR integrations and Felons Brewing Co. pilots. Deeper POS API integrations initiated after validation of the MVP.
    *   **Q4 (Phase 4) - Shout Pro & Premium Customization**: Release $3.99 AUD/month subscription featuring our custom OCR receipt scanning engine and premium theme customization.


### Slide 10: The Ask & Capital Allocation
*   **Visual**: A clean pie chart showing capital deployment.
*   **Copy**: *Seeking $500,000 AUD Pre-Seed Funding.*
*   **Allocation**:
    *   **60% Product & Engineering**: Building out the robust monorepo, payment integrations, and WebSocket infrastructure.
    *   **30% Growth & Venue Partnerships**: Executing venue pilots, marketing campaigns, and user referral credits.
    *   **10% Operations & Compliance**: Standard operations, legal, and financial licensing.

### Slide 11: The Team
*   **Visual**: Headshots of the leadership team.
*   **Roles**:
    *   **Sarah (CEO)**: Business strategy and monetization.
    *   **Liam (PM)**: Feature scoping and agile timelines.
    *   **Chloe (Sales & Marketing)**: Customer retention, branding, and growth loops.
    *   **Aiden (Tech Lead)**: Technical architecture and security.
    *   **Kong (Developer)**: Frontend & backend implementation.
