# 🧠 TontiFlex Project Context Helper

## 📝 Project Overview
TontiFlex is a web-based platform that digitalizes the management of tontines and savings accounts for Decentralized Financial Systems (SFDs). It enables clients to:
- Register and join tontines.
- Make contributions via Mobile Money (MTN/Moov).
- Manage savings accounts (deposits/withdrawals).
- Apply for loans.
- Access dashboards and transaction histories.

The system adheres to regulations from UEMOA and BCEAO, and includes role-based access control and approval workflows.

## 🧩 Key Entities & Roles

### 👤 Client
- Registers with personal info (name, phone, email, address, profession).
- Joins tontines with daily contribution amount + ID document.
- Manages contributions via Mobile Money.
- Can request withdrawals.
- Can open a savings account or apply for a loan.

### 👨‍💼 Agent SFD
- Validates client IDs, savings account requests, and withdrawal approvals.
- Has a dashboard of pending requests + action history.

### 🧑‍💼 Superviseur SFD
- Reviews loan applications.
- Sets interest rates and repayment schedules.
- Can edit submitted forms and forward to admin if needed.
- Tracks repayment status.

### 🧑‍💻 Admin SFD
- Creates and configures tontines.
- Validates loans.
- Consults stats and agent/supervisor logs.
- Can deactivate user or agent accounts.

### 🛠 Admin Platform
- Manages overall user accounts.
il peut creer, suspendre, supprimer les compte des clients, agentSFD, AdminSFD, superviseurSFD
Il peut ajouter, supprimer, susprendre des SFD.

## 🔐 Business Rules Summary

- **Tontine Membership:** requires valid ID, contribution within min/max limits, Mobile Money fee payment.
- **Contribution Cycles:** Fixed amount per client, 31-day cycles, 1st contribution per cycle is SFD commission.
- **Withdrawals:** Must be validated by agent; SFD funds must be sufficient.
- **Savings Accounts:** Requires valid ID + photo, agent approval, and payment of creation fee.
- **Loans:** Allowed only if savings account is > 3 months old. Disbursement is in person. Repayments via Mobile Money.

## 🔌 Key Functional Requirements

- Integration with MTN and Moov Mobile Money APIs.
- Email/SMS notifications for confirmations, rejections, and loan repayments.
- Role-based dashboards (client, agent, supervisor, admin).
- Tracking of all transactions and actions in a secure DB.
- Real-time status updates and validations.

## 🔐 Non-Functional Requirements

- Regulatory compliance (UEMOA, BCEAO).
- Full transaction traceability and data protection (ID, loan docs).
- Fast and reliable user experience with Mobile Money.
- MVP priority features: registration, tontine joining, contributions, withdrawals, savings account, basic loan process.

---

> ✅ This context should be loaded into Copilot using `.github/copilot-instructions.md` so it can assist with intelligent, domain-aware code suggestions.



