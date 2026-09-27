# Security Policy

## Purpose
IP-SAKTI SAHAYAK may eventually process intellectual-property, research and regulatory information. Security and privacy are core engineering requirements.

## Never commit
- API keys, passwords or tokens
- Private keys or certificates containing private material
- Database credentials
- Production .env files
- Real authentication databases
- Personal or confidential user data
- Restricted/proprietary source documents without redistribution permission
- Local vector indexes or private uploads
- Session cookies/browser credentials
- Logs containing sensitive personal information
- Local virtual environments

## Local configuration
Use a local .env file or approved secret manager.

Example:
~~~env
LLM_API_KEY=your_local_value
DATABASE_URL=your_local_value
JWT_SECRET=your_local_value
~~~

The real .env file must never be pushed.

## If a secret is exposed
1. Revoke or rotate it immediately.
2. Remove it from the working tree.
3. Check repository history.
4. Replace the credential wherever it was used.
5. If necessary, rewrite Git history using an appropriate secret-removal process.
6. Review relevant access logs.

Deleting a file does not invalidate an already exposed credential.

## Data handling
Use synthetic/de-identified data for development and demonstrations. Do not upload real personal, medical, confidential business or restricted legal documents merely to test the prototype.

## Frontend rule
Never put private API keys in HTML, CSS, browser JavaScript or public configuration. Browser code is visible to users.

## Production requirements
Before production deployment implement HTTPS, secure authentication, RBAC, secret management, input validation, rate limiting, audit logging, secure CORS, dependency scanning, vulnerability testing, backup/recovery, retention/deletion controls, privacy review and source licensing review.

## Vulnerability reporting
Do not publish credentials or exploit details in a public issue. Contact the repository maintainers through a private security channel.

This is an engineering baseline, not a legal certification or guarantee of compliance.
