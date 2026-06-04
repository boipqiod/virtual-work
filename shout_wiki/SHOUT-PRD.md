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

---

## 3. Minimum Viable Product (MVP) Scope
- **Sprint 1**: Setup monorepo structure, Node Express backend, Next.js frontend, and Socket.io basic chat room.
- **Sprint 2**: Integrate Plaid Link & transaction picker UI (with Mock mode).
- **Sprint 3**: Integrate Stripe card payment form and live progress bar updates.
