# DataViz Dash freemium plan

## Commercial pricing ladder

| Plan | Positioning | Price | Delivery status |
| --- | --- | ---: | --- |
| Free | Individual experimentation | ₹0 | Available |
| Pro | Freelancer / analyst | ₹499/month | Entitlements implemented; checkout pending |
| Business | Teams + larger usage | ₹1,999–₹2,999/month | Planned |
| Agency | Multiple clients/workspaces | ₹4,999–₹9,999/month | Planned |
| Enterprise | SSO, private deployment, SLA | Custom | Contact-led roadmap |
| Government | Private/on-prem deployment + support | Custom annual contract | Contact-led roadmap |

The pricing page may market the complete ladder, but it must distinguish current
entitlements from roadmap capabilities. Business and above must not be activated
until their team/workspace, security, deployment, and support commitments are
implemented and operationally supportable.

## Recommended limits

The product should keep its core cleaning workflow useful on the Free plan while
charging for larger workloads, persistence, and professional exports.

| Capability | Free | Pro |
| --- | --- | --- |
| File types | CSV, XLS, XLSX | CSV, XLS, XLSX |
| Maximum upload | 50 MB | 100 MB |
| Maximum rows per dataset | 100,000 | 100,000 |
| Total uploaded data | 150 MB | 5 GB |
| Saved datasets | 3 | 25 |
| Saved dashboards | 2 | 25 |
| Visuals per dashboard | 4 | 12 |
| Dashboard pages | 1 | 20 |
| Chart data | First 50,000 rows | Up to 100,000 rows |
| Basic cleaning | Included | Included |
| Cleaned CSV download | Included | Included |
| Chart PNG export | Included | Included |
| Dashboard JSON export | Upgrade required | Included |
| Print / PDF export button | Upgrade required | Included |
| Workspace identity | Anonymous or signed-in | Signed-in account |
| Data retention | 90 days from creation | 90 days from creation |
| Longer retention | Separate Extended Storage add-on | Separate Extended Storage add-on |

The Pro 5 GB allowance is a total account quota measured from uploaded source
sizes. It is not a 5 GB single-file limit. The synchronous Flask and Pandas
pipeline currently caps one upload at 100 MB; multi-gigabyte individual files
will require direct object-storage uploads and asynchronous, chunked processing.

Workspace retention is independent of product entitlement. Datasets, derived
rows, and dashboards expire 90 days after their original creation date on every
standard plan. Users who need longer retention must arrange the separate
Extended Storage add-on before expiry; its capacity, duration, and price are
quoted independently from the user's Free, Pro, Business, or Agency plan.

## Enforcement model

Limits must be checked on the server. Hiding a button in JavaScript is only a
user-interface treatment and cannot protect paid features.

1. Identify the workspace or signed-in user.
2. Resolve the effective plan from the database.
3. Check the relevant entitlement before every protected API operation.
4. Return a structured `403` response when a limit is reached:

   ```json
   {
     "error": "Upgrade to Pro to use this feature.",
     "code": "PLAN_LIMIT_REACHED",
     "feature": "dashboard_pdf_export",
     "upgrade_url": "/pricing"
   }
   ```

5. Let the frontend open the pricing/paywall page from that response.

Suggested MongoDB collections:

- `users`: identity, email, status, and timestamps.
- `subscriptions`: provider customer/subscription IDs, plan, status, period end.
- `usage`: per-user counters and reset periods when usage-based limits are added.
- Existing `datasets` and `dashboards`: replace anonymous ownership with a stable
  user ID after sign-in, while still allowing a temporary anonymous workspace.

## Payment lifecycle

1. User selects a self-serve paid plan on `/pricing`, starting with Pro.
2. Server creates a hosted checkout session.
3. Payment provider redirects back to a success or cancellation page.
4. A signed webhook updates the subscription in MongoDB.
5. The entitlement service reads the stored subscription status.

The browser redirect must never activate Pro by itself. The verified webhook is
the source of truth. Webhook processing must verify signatures and be idempotent.

## Delivery phases

1. **Capacity:** support the 100 MB / 100,000-row technical ceiling and account quotas safely. *(Implemented)*
2. **Entitlements:** add Free and Pro plan definitions plus server-side checks. *(Implemented)*
3. **Identity:** add email-based accounts and let users claim an anonymous workspace. *(Implemented)*
4. **Paywall:** add `/pricing`, upgrade prompts, and plan-limit messaging. *(Implemented without checkout)*
5. **Billing:** connect Pro checkout, verified webhooks, subscription management, and cancellation handling.
6. **Teams:** implement Business memberships, roles, shared workspaces, and higher quotas.
7. **Multi-workspace:** implement Agency client isolation and account-level administration.
8. **Private deployment:** implement Enterprise/Government SSO, deployment, security, SLA, and support workflows.

Real paid access should not launch without identity. A browser cookie can be
cleared or copied, so it cannot safely own a subscription.
