# Plaid Onboarding and Verification Guidelines

This document outlines the user onboarding strategy, conversion optimization design patterns, and validation guidelines for the Plaid bank integration within **Shout**. The objective is to minimize user friction during the linking flow while building maximum brand trust and security assurance.

---

## 1. Growth Metrics & Conversion Goals

Linking a bank account is the single most critical friction point in the Shout user journey. If users drop off here, they cannot split bills or initiate transactions. We are targeting the following onboarding KPIs for our MVP launch:

*   **Plaid Link Success Rate**: 85%+ (percentage of users who initiate and successfully complete Plaid authentication).
*   **Aesthetic Trust Rating**: 9/10 in user testing surveys.
*   **Time-to-Link**: Under 45 seconds average completion time.
*   **Drop-off Rate (MFA/Auth)**: Less than 10% on security screens.

---

## 2. Onboarding Friction Points & Mitigation Strategies

Our user testing highlights three major friction areas during the bank connection flow. We must implement the following design solutions to maintain high user trust and prevent screen abandonment.

### A. The "Password Panic" (Security & Trust Deficit)
*   **The Friction**: Young Aussie users are highly defensive about inputting their actual bank passwords into a third-party flow. When the Plaid interface opens, many suspect phishing or an "aesthetic crime" interface.
*   **Mitigation Rules**:
    1.  **Pre-Link Trust Screen (The Gateway)**: Never throw the user directly into Plaid Link. We must display a customized, beautifully designed Shout transition sheet first.
    2.  **Clear Copywriting**: Use direct, jargon-free explanations:
        *   *Do say*: "Shout uses bank-grade security to link your account. We only receive read-only transaction history. We never see your login details, and we cannot move your money."
        *   *Do NOT say*: "By authorizing, you grant Shout API tokens to scrape and persist transaction datasets."
    3.  **Visual Assurances**: Display security lock icons alongside the Plaid logo. Ensure a vibrant, high-contrast CTA ("Securely Link Bank") is visible at the bottom.

### B. Setup Timing & Contextual Triggers
*   **The Friction**: Prompting bank linking immediately during the signup flow kills retention. Users want to explore the room-based chat and vibe with the UI before committing sensitive data.
*   **Mitigation Rules**:
    1.  **Exploration Mode**: Allow users to register, create groups, and chat without linking a bank account.
    2.  **Contextual Call to Action**: Trigger Plaid Link *only* when the user performs a high-intent action:
        *   Clicking **"Split a Bill"** inside the chat group.
        *   Tapping **"Select Bill from Bank"** on the Shout Card.
    3.  **Value-Driven CTA**: Anchor the action to a clear benefit: *"Connect your bank to pull in your last round from Felons Brewing Co. automatically."*

### C. The Institution Search Friction
*   **The Friction**: Searching for smaller regional banks or credit unions can be confusing, and users hate scrolling through hundreds of institutions.
*   **Mitigation Rules**:
    1.  **Popular Banks Quick-Select Grid**: Display a grid of the most common Australian institutions (CommBank, Westpac, ANZ, NAB, Macquarie, ING) right above the search bar. Use high-resolution, recognizable brand tiles.
    2.  **Search Autofocus**: When the search modal opens, autofocus the keyboard instantly to minimize thumb-travel.

---

## 3. High-Converting UI Patterns & Aesthetics

Aiden's text-only minimalist screens won't cut it here—the Plaid onboarding must feel premium, fluid, and modern.

### A. Loading States & Micro-animations
*   **Shimmer Placeholders**: During database synchronization (public token exchange), do not use raw spinners. Use CSS-shimmer gradient blocks that mimic the transaction list layout.
*   **Progressive Messages**: Display dynamic progress notifications that reassure the user the app is working:
    1.  *"Verifying connection..."* (0–1s)
    2.  *"Syncing transaction logs..."* (1–3s)
    3.  *"Creating secure workspace..."* (3s+)

### B. Celebration State (The Success Loop)
*   Once Plaid returns a successful account exchange, trigger an immediate success micro-animation:
    *   A subtle burst of colorful confetti.
    *   A smooth slide-up animation showing the user's latest transactions.
    *   A friendly green checkmark confirming the link status: *"Sweet! Your bank is securely linked."*

---

## 4. Verification & Testing Guidelines

To ensure the onboarding flow remains friction-free and correct, developers and product testers must follow these verification guidelines:

### A. Core Plaid Flow Validation
1.  **Transition Check**: Validate that clicking the "Link Bank" button triggers the **Pre-Link Trust Screen** first, and that the Plaid SDK only launches after clicking the secure CTA.
2.  **Sandbox Credentials**: During local verification, use the Plaid Sandbox credentials:
    *   **Username**: `user_good`
    *   **Password**: `pass_good`
3.  **MFA Scenario Testing**: Verify the flow doesn't crash when encountering MFA challenges in sandbox:
    *   **Username**: `user_good`
    *   **Password**: `mfa_device` (Verify the OTP verification code screen loads and processes successfully).

### B. Resilience & Error Boundaries
1.  **Database Outage Simulation**: Simulate database lockouts or API timeouts during the public token exchange. Verify that the UI displays a clean, user-friendly error card (*"We couldn't connect to your bank right now—let's try again in a sec"*) instead of crashing or showing raw stack traces.
2.  **MFA Failure Handling**: Validate that inputting an incorrect MFA code allows the user to re-enter credentials gracefully without kicking them out of the Plaid session.
3.  **Fallback Mode Toggle**: Ensure that if Plaid API credentials are not detected in the environment (e.g. `PLAID_CLIENT_ID` is missing), the interface displays a clear **Mock Mode** banner informing the user that they are viewing simulated local Brisbane transactions (e.g., Felons Brewing Co.).
