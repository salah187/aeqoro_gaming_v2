# AEQORO Gaming — Telegram Mini App starter

English-language, mobile-first Telegram Mini App starter with referral attribution and a partner link that remains disabled until you configure an approved affiliate partner.

## Included
- Flask backend and SQLite database
- Telegram Web App `initData` HMAC verification
- Telegram user profile and referral tracking (`startapp=ref_<telegram_id>`)
- Click tracking
- Mobile-first English interface
- Privacy notice template
- No deposit, betting, wallet, or withdrawal handling

## 1. Create the Telegram bot
1. Open https://t.me/BotFather and send `/newbot`.
2. Save the bot token privately.
3. Set the bot username in your deployment environment as `TELEGRAM_BOT_USERNAME` (without `@`).
4. Never put `TELEGRAM_BOT_TOKEN` in frontend JavaScript or commit it to GitHub.

## 2. Deploy
Deploy this repository to a Python-capable host. Set the start command to `gunicorn app:app` if the host does not use the included Procfile.

Environment variables:
- `TELEGRAM_BOT_TOKEN`: required for authenticating Mini App requests.
- `TELEGRAM_BOT_USERNAME`: the bot username without `@`.
- `REQUIRE_TELEGRAM_AUTH=true`: keep enabled in production.
- `DATABASE_PATH`: optional persistent database path if supported by the host.
- `APPROVED_PARTNER_NAME`: set only after written affiliate approval.
- `AFFILIATE_URL`: approved affiliate URL only; never insert a link before permission.
- `PORT`: supplied by some hosts.

**Important hosting limitation:** SQLite data stored on an ephemeral filesystem may be lost on redeploy/restart. Use a persistent disk or managed database if the host offers one for free; otherwise this starter is suitable for testing, not reliable production referral accounting.

## 3. Configure Telegram Mini App
Use BotFather's Mini App / Web App configuration options to set the deployed HTTPS URL. BotFather menus may change; follow the current prompts. The public app URL must use HTTPS.

For direct referral deep links, Telegram supports Mini App start parameters. The referral URL format in this starter is:
`https://t.me/<BOT_USERNAME>?startapp=ref_<TELEGRAM_USER_ID>`

The backend validates Telegram `initData` and reads the verified `start_param`. Test this flow from Telegram itself, not only in a normal browser.

## 4. Local testing
Install Python 3.10+ and dependencies:
```bash
pip install -r requirements.txt
```
Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME`, then run:
```bash
python app.py
```
The app listens on port 5000. Since authentication is enabled by default, API calls must come from Telegram with valid `initData`.

For a temporary local-only preview, set `REQUIRE_TELEGRAM_AUTH=false`. **Never use this setting on a public deployment** because it permits spoofed demo identities.

## 5. Affiliate compliance checklist
Before setting partner environment variables:
- Obtain written approval for Telegram Mini Apps and your planned traffic source.
- Confirm the countries the program permits you to target and whether your residence is eligible.
- Review applicable laws and platform policies; do not assume a global audience means all countries are permitted.
- Add the partner's required disclosures and age/location restrictions.
- Do not describe click counts as qualified referrals or commissions.
- Only show commission totals supplied by the partner's reporting/API, if available and permitted.

This starter does not integrate with any casino API and does not claim that any company has approved the project.
