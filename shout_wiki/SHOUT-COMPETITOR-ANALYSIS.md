# Competitor Analysis: Beem vs. Splitwise

This research maps out the local competitive landscape for **Shout** (see [SHOUT-PRD.md](file:///Users/kong/Desktop/Develop/VirtualWork/shout_wiki/SHOUT-PRD.md)), focusing on key players **Beem** and **Splitwise** to define our competitive advantages and outline monetization paths for the Shout product roadmap.

---

## 1. Competitor Deep Dives

### Competitor A: Beem (formerly Beem It)
* **Overview**: A popular Australian peer-to-peer (P2P) instant payment app, recently acquired by Bolt Group (April 2026) from Australian Payments Plus (AP+).
* **Target Audience**: Young Australians needing quick card-to-card money transfers.
* **Core Features**:
  * Instant P2P money transfers using usernames/handles (no BSB/account numbers required).
  * Basic group bill-splitting requests.
  * BPAY support for splitting utility and household bills.
  * Storage for digital loyalty and gift cards.
  * Cashback rewards for in-app shopping.
* **Monetization Model**:
  * Historically free for consumers.
  * Bolt Group plans to monetize by expanding Beem into a broader "everyday money app" offering transaction and savings accounts, multi-currency wallets, and investment services.
* **Key Limitations & Gaps**:
  * **Dry Utility UX**: It feels like a standard banking utility app. There is no social connection, chat stream, or interactive element.
  * **No Transaction Syncing**: Users cannot sync their external bank transactions via Open Banking (Plaid) to split a past dinner bill. Every expense has to be entered manually or split from a card payment.
  * **No Venue Integrations**: Lacks ordering/splitting integrations at the point-of-sale or table QR codes.

### Competitor B: Splitwise
* **Overview**: The global market leader in group expense tracking and ledger management, operating on a freemium model.
* **Target Audience**: Flatmates, travel groups, and social circles tracking ongoing shared costs.
* **Core Features**:
  * Persistent group ledgers showing who owes whom.
  * Flexible splitting options (equal, unequal shares, percentages).
  * OCR receipt scanning, currency conversion, and search history (Pro only).
* **Monetization Model**:
  * **Splitwise Pro Subscription**: $4.99 USD/month or $39.99 USD/year.
  * **Cluttered In-App Ads**: Running banner ads on the free tier.
  * **Usage Restrictions**: Imposes a daily transaction limit on free users to force Pro upgrades.
* **Key Limitations & Gaps**:
  * **No Integrated Payments in Australia**: Splitwise Pay is limited to the US. Australian users are forced to leave the app, open their banking app, transfer funds manually, and return to Splitwise to record the settlement.
  * **Dry Spreadsheet Aesthetic**: Highly functional but lacks visual appeal and modern micro-animations. It feels like tracking homework rather than enjoying a night out.
  * **High User Friction**: The daily transaction limit and aggressive ad prompts are causing significant user dissatisfaction (evident in recent App Store reviews).

---

## 2. Shout's Competitive Advantages

| Feature / Aspect | Beem | Splitwise | Shout |
| :--- | :--- | :--- | :--- |
| **Primary Focus** | Card P2P Payments | Debt Tracking Ledger | Social Bill Splitting |
| **Real-time Group Chat** | No | No | **Yes (Socket.io)** |
| **Direct Aussie Payments** | Yes (Debit Card P2P) | No (External Transfer Only) | **Yes (Stripe Sandbox)** |
| **Bank Transaction Sync** | No | No | **Yes (Plaid Sandbox)** |
| **Aesthetics & Micro-animations**| Basic Utility | Text-heavy Ledger | **Premium, Dynamic, Custom Cards**|
| **Venue Integrations** | No | No | **Yes (Table QR Codes)** |

Shout bridges the gap between Splitwise's ledger tracking and Beem's payment execution, embedding the entire experience within a modern, social-first chat interface.

---

## 3. Shout Monetization Paths

To reach our seed-stage goals and secure $500,000 AUD in funding (see [MILESTONES.md](file:///Users/kong/Desktop/Develop/VirtualWork/shout_wiki/MILESTONES.md)), we will employ a multi-layered monetization strategy:

1. **Transaction Take Rate (Primary)**
   * **Mechanism**: A 1.5% convenience fee markup on Stripe card payment transactions.
   * **Why it works**: Users are willing to pay a micro-fee for the extreme convenience of instant card splitting inside chat, avoiding the pain of copying BSB/account numbers and waiting for bank transfers.
2. **Venue Commissions (B2B Partnerships)**
   * **Mechanism**: Revenue share/commission from partner venues (e.g., *Felons Brewing Co.*) for orders driven through our table QR codes.
   * **Why it works**: Venues get higher average order values and faster table turnover, while Shout captures a percentage of the bill. See [SHOUT-MARKETING-PLAN.md](file:///Users/kong/Desktop/Develop/VirtualWork/shout_wiki/SHOUT-MARKETING-PLAN.md) for venue details.
3. **Instant Settlement Premium (Express Payouts)**
   * **Mechanism**: Charge a flat 1% fee for instant payout to external bank accounts, while standard 2-3 business day payouts remain free.
4. **Shout Pro (Premium Features)**
   * **Mechanism**: A premium subscription ($3.99 AUD/month) for power users.
   * **Features included**:
     * OCR receipt scanning and auto-splitting.
     * Custom chat aesthetics (vibrant themes, premium group stickers, animated cards).
     * Extended transaction history search.

---

## 4. Product Roadmap Recommendations

* **Phase 1: Zero-friction MVP (June)**: Deliver the core chat and split payment flow using Socket.io and Stripe/Plaid sandboxes (see [SHOUT-TECH-SPEC.md](file:///Users/kong/Desktop/Develop/VirtualWork/shout_wiki/SHOUT-TECH-SPEC.md)).
* **Phase 2: Viral Referral Loops (Q3)**: Implement a $5 AUD referral program to drive user acquisition.
* **Phase 3: Venue Partnerships (Q3)**: Launch table QR ordering integrations with *Felons Brewing Co.*
* **Phase 4: Shout Pro Launch (Q4)**: Roll out OCR scanning and premium custom themes.