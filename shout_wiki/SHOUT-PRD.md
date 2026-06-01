# [PRD] Shout - Social Bill Splitting App

## 1. Executive Summary
**Shout** is a mobile-first, social fintech web application designed to solve the group dining and bill-splitting challenge for young Australians (e.g., hanging out at *Felons Brewing Co.* in Brisbane). 

Users can invite friends into a real-time group chat, sync bank transaction logs via Plaid, select a bill, and split it. Group members pay their share instantly via Stripe, with real-time UI updates powered by WebSockets.

---

## 2. Core User Stories & Features

### Feature 1: Real-time Group Chat (Socket.io)
- **User Story**: As a user, I want to create a chat group and message my friends in real-time so we can coordinate our outings and split bills easily.
- **Requirements**:
  - Room-based chat interface.
  - Interactive "Shout Card" showing the active bill split details inside the chat stream.

### Feature 2: Bank Transaction Sync (Plaid Sandbox)
- **User Story**: As a group creator, I want to connect my bank account and select a transaction so we don't have to enter the bill details manually.
- **Requirements**:
  - Plaid Link flow to connect bank account.
  - Fetch recent transactions list and let the user tap one to initiate a split.
  - Provide a fallback "Mock Mode" for testing without API keys.

### Feature 3: Card Payments (Stripe Sandbox)
- **User Story**: As a group member, I want to pay my split share instantly using a debit/credit card so I don't have to deal with bank transfers.
- **Requirements**:
  - Stripe Elements integration for card entry.
  - Process payment and instantly broadcast update to the group.

### Feature 4: Mobile-First Responsive PWA Layout
- **Requirements**:
  - Optimized for mobile viewports.
  - Centered mock phone frame on desktop screens.

### Feature 5: Instant Settlement & Express Payouts
- **User Story**: As a user who is owed money, I want to cash out my balance immediately to my external bank account so that I don't have to wait days for standard processing.
- **Requirements**:
  - Direct integration with payment APIs for express payouts.
  - Dynamic fee display (1% premium fee for express payout vs. free standard payout in 2-3 business days).

### Feature 6: Shout Pro Subscription Tier
- **User Story**: As a power user, I want premium customization and tools so I can manage my group spending with ease.
- **Requirements**:
  - Optical Character Recognition (OCR) for receipt scanning and automated line-item splitting.
  - Customizable UI themes, animated cards, and premium chat sticker packs.
  - Advanced search features for historical transaction logs.

---

## 3. Minimum Viable Product (MVP) Scope
- **Sprint 1**: Setup monorepo structure, Node Express backend, Next.js frontend, and Socket.io basic chat room.
- **Sprint 2**: Integrate Plaid Link & transaction picker UI (with Mock mode).
- **Sprint 3**: Integrate Stripe card payment form and live progress bar updates (including Stripe's convenience fee pricing display).

---

## 4. Monetization Strategy
To ensure sustainable seed-stage growth and position Shout for a $500,000 AUD pre-seed round (outlined in [MILESTONES.md](file:///Users/kong/Desktop/Develop/VirtualWork/shout_wiki/MILESTONES.md)), we will utilize a multi-layered monetization model that captures value from both convenience and B2B partnerships:

1. **Transaction Take Rate (Primary)**:
   - **Details**: A 1.5% convenience fee markup is applied to all Stripe-processed card payment transactions.
   - **Rationale**: Captures value by removing the friction of manual bank transfers (BSB/account numbers) during outings.

2. **B2B Venue Partnerships & Commissions**:
   - **Details**: Revenue share/commission from partner venues (starting with our launch partner, *Felons Brewing Co.*) for orders driven through table QR codes.
   - **Rationale**: Increases average order values and speeds up table turnover for venues while giving Shout a B2B revenue stream. For more details on venue partnerships, see the [SHOUT-MARKETING-PLAN.md](file:///Users/kong/Desktop/Develop/VirtualWork/shout_wiki/SHOUT-MARKETING-PLAN.md).

3. **Express Payout Premium**:
   - **Details**: A flat 1.0% fee is charged to users who choose instant settlement/payout to their bank accounts. Standard payouts (2-3 business days) remain free.
   - **Rationale**: Monetizes liquidity convenience for users who want their cash immediately.

4. **Shout Pro Subscription ($3.99 AUD/Month)**:
   - **Details**: A premium tier offering power features:
     - OCR receipt scanning and auto-splitting.
     - Custom chat themes (vibrant visual styles, premium group stickers, animated cards).
     - Extended transaction history search.
   - **Rationale**: High-margin recurring revenue targeting heavy users (e.g., housemates and frequent travelers).

---

## 5. Competitor-Informed Product Roadmap
Our product roadmap is refined based on competitive analysis of local players (Beem) and global leaders (Splitwise), as detailed in [SHOUT-COMPETITOR-ANALYSIS.md](file:///Users/kong/Desktop/Develop/VirtualWork/shout_wiki/SHOUT-COMPETITOR-ANALYSIS.md). It bridges the gap between debt tracking ledgers and real-time payments:

### Phase 1: Zero-Friction MVP (June / Sprints 1-3)
- **Focus**: Core chat room, Plaid transaction sync (w/ Mock Mode), and Stripe card payment flow.
- **Goal**: Deliver a working prototype to showcase real-time web-socket progress splits to angel investors.
- **Monetization Integration**: Basic calculation and display of the 1.5% Stripe transaction convenience fee during split checkout.
- **Standards & Spec Alignment**: Built following [SHOUT-TECH-SPEC.md](file:///Users/kong/Desktop/Develop/VirtualWork/shout_wiki/SHOUT-TECH-SPEC.md) architecture and [CODING-STANDARDS.md](file:///Users/kong/Desktop/Develop/VirtualWork/shout_wiki/CODING-STANDARDS.md) resilience guidelines.

### Phase 2: Viral Growth Loops & Social Referral (Q3 Start / Sprint 4)
- **Focus**: Launching referral programs and social sharing.
- **Key Features**:
  - **Referral Loop**: $5 AUD sign-up/split credit for both referrers and new active users.
  - **Social Sharing**: Direct share-to-story features for Instagram and group message apps.
- **Target CAC**: < $2.50 AUD.

### Phase 3: B2B Venue Integration & Table QR Ordering (Q3 Mid-Late / Sprint 5)
- **Focus**: Partnering with physical dining spots, starting with *Felons Brewing Co.*
- **Key Features**:
  - **Table QR Codes**: Direct room generation and billing link upon scanning table QR codes.
  - **Promotional Splits**: "It's your shout!" weekend promotions featuring a 5% discount on bills split and paid instantly via Shout.
  - **Venue Commission Setup**: Express API integration with POS software to automate B2B commissions.

### Phase 4: Shout Pro Launch & Premium Customization (Q4 / Sprint 6)
- **Focus**: Subscription tier rollout and high-value features.
- **Key Features**:
  - **OCR Engine**: Scanner to parse itemized dining receipts.
  - **Pro Tier Billing**: Subscription billing pipeline via Stripe.
  - **Premium Themes**: Rich UI animations, themed card components, and custom chat aesthetics.