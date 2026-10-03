# Security practices

## Encryption
All traffic between your browser or the mobile app and Acme Invoicing is encrypted with TLS 1.2 or higher. Stored data is encrypted at rest with AES-256.

## Sign-in protection
Passwords are stored as one-way hashes, so even our own staff cannot read them. After 5 failed sign-in attempts the account is locked for 15 minutes. You are signed out automatically after 8 hours of inactivity. You can add two-factor authentication for extra protection.

## Access by our staff
Only a small number of Acme Invoicing staff can reach production data. Access is logged, and staff look at your account only to answer a support request that you started.

## Backups
We take encrypted backups of the database every day.

## Report a security problem
If you think you have found a security problem, email security@acme-invoicing.example. We reply within 2 business days.

## What you can do
- Use a long, unique password.
- Turn on two-factor authentication in Settings > Security.
- Give each team member the lowest role that lets them do their job.
- Remove people from Settings > Team as soon as they leave.

## Related articles
See "Two-factor authentication (2FA)", "Reset your password" and "Team roles and permissions".
