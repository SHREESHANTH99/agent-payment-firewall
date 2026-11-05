# Contributing to Agent Payment Firewall

Thank you for your interest in contributing to the Agent Payment Firewall!

## Development Guidelines
1. **Never Commit Secrets**: Do not commit API keys, `.env` files, or sandbox tokens.
2. **Sandbox Only**: All PayPal integrations must strictly target sandbox hosts (`https://api-m.sandbox.paypal.com`).
3. **Integer Cents**: All money fields in models and logic must remain integer cents.
4. **Test Before Committing**:
   - Backend tests: `pytest backend/tests`
   - Dashboard tests: `cd dashboard && npm test && npm run build`
5. **Evaluation Protocol Freeze**: Do not modify frozen prompt versions or evaluation decision rules without pre-registering changes.
