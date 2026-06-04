# [Competitor Analysis] Beem vs. Splitwise vs. Shout

To make Shout the go-to app for group bill splitting in Australia, we need to understand exactly where the current market leaders are falling short. 

Here is our breakdown of **Splitwise** and **Beem (formerly Beem It)**, and how Shout's unique positioning is going to win over Aussie users.

---

## 1. Splitwise: The Administrative Spreadsheet
Splitwise is the global giant for tracking IOUs, but it feels more like an accounting tool than a social app.

*   **Pros**:
    *   Excellent for long-term expense tracking (e.g., housemates sharing rent and bills over months).
    *   Flexible split types (by percentage, shares, adjustment).
*   **Cons**:
    *   **No Integrated Australian Payments**: This is their biggest weakness. Aussie users can't actually settle debts inside the app. They have to leave Splitwise, open their banking app, make a PayID/bank transfer, and then manually come back to tap "Record Payment".
    *   **Low Engagement / "Spreadsheet Vibe"**: It is transactional. People only open it when they need to resolve debts, leading to awkward "friendly reminders."
    *   **Aggressive Monetization**: Recently put basic features (like OCR receipt scanning and search history) behind a Paywall, frustrating long-time users.

---

## 2. Beem: The Payment Utility
Beem is owned by eftpos (originally BPAY/major banks) and is well-known in Australia for instant, card-to-card payments.

*   **Pros**:
    *   Instant, free peer-to-peer transfers using debit cards.
    *   Strong local trust and brand recognition in Australia.
*   **Cons**:
    *   **Clunky Group UX**: Creating groups and splitting bills is a multi-step, rigid process.
    *   **Poor Social Integration**: While they have a chat feature, the vibe is sterile and it's rarely used for actual conversation. It's treated purely as a utility.
    *   **No Transaction Sync**: Users must manually enter transaction details or upload screenshots. There is no automated bank feed integration to split a real-world transaction from a credit card or bank account.

---

## 3. Shout: The Social Fintech Solution
Shout combines the social immediacy of a group chat with the utility of instant payments and bank synchronization. We are designing for the *experience* of going out with friends (starting with our launch partner, **Felons Brewing Co.**).

| Feature | Splitwise | Beem | Shout |
| :--- | :--- | :--- | :--- |
| **Primary Vibe** | IOU Spreadsheet | Payment Utility | Social Group Chat |
| **Australian P2P Settlement** | ❌ None (external bank transfer) |  Instant (debit cards) |  Instant (Stripe in-chat) |
| **Real-time Chat** | ❌ None | ⚠️ Basic / Sterile |  Socket.io Group Chat |
| **Bank Transaction Sync** | ❌ Manual entry | ❌ Manual entry |  Plaid Sandbox Sync |
| **Split UX** | Tabular, rigid | Multi-step form | Interactive "Shout Cards" |

### Our Secret Sauce (How Shout Wins)
1.  **In-Chat "Shout Cards"**: Instead of navigating menus, a user simply posts a "Shout Card" directly into the Socket.io chat room. Friends see the card and tap to pay their share immediately in the thread.
2.  **Plaid Transaction Sync**: The group creator can securely connect their bank account via Plaid, pull their real-time transaction history, and instantly split the $150 round of drinks from Felons Brewing Co. without manual entry.
3.  **Low Friction Onboarding**: Next.js mobile-first PWA design allows guest users to join the chat and settle their share via Stripe Elements card payments without being forced through a sign-up flow.
