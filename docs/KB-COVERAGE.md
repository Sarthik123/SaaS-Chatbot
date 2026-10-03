# Knowledge base coverage

The fake company is **Acme Invoicing** (a made-up invoicing and billing app). Everything in
`data/demo_kb/` is invented. This file says what the 25 articles DO cover, what they deliberately
do NOT cover, and a few "near-miss" gaps. It is the source for the "I don't know" test questions
in Phase 5 (the bot must refuse the second and third lists).

An automatic test (`api/tests/test_demo_kb.py`) checks that the topics in lists B and C really do
not appear in any article, so the refusal questions stay honest.

## A. Topics the articles DO cover (25 articles)

| Article (file name) | Covers |
|---|---|
| getting-started-create-your-account | sign-up, 14-day trial, company profile |
| create-an-invoice | line items, numbering, due dates, attachments, void |
| recurring-invoices | schedules, auto-send, limits per plan |
| payment-reminders | default reminder schedule, placeholders |
| late-fees | flat or percentage fees, grace period, cap |
| taxes-and-vat | tax rates, rounding, VAT numbers, reverse charge |
| multiple-currencies | supported currencies, exchange rates |
| refunds-and-credit-notes | credit notes, voiding, subscription refund |
| import-customers-from-csv | columns, limits, duplicates |
| export-your-data | CSV export, PDFs, full export |
| team-roles-and-permissions | four roles, user limits |
| reset-your-password | reset link, lockout |
| two-factor-authentication | authenticator app, recovery codes |
| connect-an-accounting-tool | two fictional accounting tools, sync |
| plans-and-pricing | three plans, annual billing |
| cancel-your-subscription | how to cancel, what happens after |
| data-privacy-and-retention | what is stored, 90-day retention |
| security-practices | encryption, sign-in protection |
| invoice-templates-and-branding | logo, colour, templates |
| the-mobile-app | what the app can do, offline drafts |
| supported-languages | app and invoice languages |
| support-hours-and-contact | channels, hours, response times |
| known-limits | numeric limits, things you cannot do |
| troubleshooting-common-problems | error codes ERR-4102, ERR-5003, ERR-6001 |
| accepting-online-payments | payment provider, fees, payouts |

Some articles overlap on purpose so that retrieval is a real test: late fees and payment
reminders; refunds and cancelling; two-factor authentication, password reset and security;
plans, limits and team roles.

## B. Topics the articles deliberately do NOT cover (the bot must say "I don't know")

| # | Topic | Example customer question |
|---|---|---|
| 1 | Payroll | Can Acme Invoicing run payroll for my staff? |
| 2 | Cryptocurrency payments | Can my customers pay me in Bitcoin? |
| 3 | Phone support | What is your support phone number? |
| 4 | On-premise hosting | Can I install Acme Invoicing on my own servers? |
| 5 | Dark mode | How do I turn on dark mode? |
| 6 | Inventory management | Can I track my stock levels? |
| 7 | Shipping labels | Can I print shipping labels? |
| 8 | Time tracking | Can I track hours worked and bill them? |
| 9 | Purchase orders | How do I create a purchase order for a supplier? |
| 10 | Expense reports | Can employees submit expense reports? |
| 11 | Online store integrations | Does it connect to my online store? |
| 12 | Reselling or white-labelling | Can I resell Acme Invoicing under my own brand? |

## C. Near-miss gaps (the topic exists, the specific fact does not)

| # | Article that is close | Fact that is deliberately missing | Example customer question |
|---|---|---|---|
| 1 | the-mobile-app | the minimum phone software version the app needs | What is the oldest iPhone software version the app works on? |
| 2 | export-your-data | how long the "export all data" download link stays available | How many days do I have to download my export? |
| 3 | plans-and-pricing | any special price for charities or students | Do you give a discount to charities? |
| 4 | late-fees | how to cancel a late fee that was already added | Can I remove a late fee for one customer? |
