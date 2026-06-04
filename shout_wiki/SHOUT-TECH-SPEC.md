# [Tech Spec] Shout Architecture & API Specification

## 1. System Architecture

```text
  [Next.js Frontend] <== WebSockets (Socket.io) ==> [Express TS Backend]
           ||                                              ||
    [Stripe Elements]                              [Plaid / Stripe SDKs]
```

---

## 2. Database Schema (File-based JSON DB)
Stored in `packages/backend/src/data/db.json` for lightweight, zero-dependency local setup.

### Data Models
- **User**: `{ id: string, name: string }`
- **Group**: `{ id: string, name: string, members: string[] }`
- **Transaction**: `{ id: string, description: string, amount: number, date: string }`
- **Split**: `{ id: string, groupId: string, transactionId: string, totalAmount: number, payers: { userId: string, share: number, paid: boolean }[] }`

---

## 3. Web Socket.io Event Spec
- **`join_room`**: Client joins a room with `{ roomId: string, userId: string }`.
- **`send_message`**: Sends `{ roomId: string, text: string, senderId: string }`.
- **`shout_created`**: Broadcasts when a split bill card is generated.
- **`payment_completed`**: Broadcasts when a member pays their share to update the progress bar in real-time.

---

## 4. REST API Endpoints

### Backend Routes (`/api/*`)
- **`GET /api/transactions`**: Fetches bank transactions (using Plaid or mock data).
- **`POST /api/plaid/create-link-token`**: Generates token for Plaid Link.
- **`POST /api/plaid/exchange-token`**: Exchanges public token for access token.
- **`POST /api/payments/charge`**: Creates a Stripe PaymentIntent for a split share.

---

## 5. Mock Sandbox Fallback
If `.env` does not contain valid Stripe or Plaid keys:
- **Plaid Mock**: Returns dummy list of transactions (e.g. `"$150 at Felons Brewing Co."`, `"$25 at West End Coffee"`).
- **Stripe Mock**: Simulates success response after a 1-second timeout.
