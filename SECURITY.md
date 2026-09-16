# Security

## API credentials

Never commit BloFin API keys, secret keys, passphrases, or a populated `.env` file.
The repository intentionally ignores `.env` and runtime logs/data. Copy `.env.example` to `.env` only on the machine running the bot.

For exchange API access, use the minimum permissions required by the bot. Do not enable transfer/withdrawal permissions. Prefer IP restrictions when available.

## Live trading

The project defaults to paper mode. Live trading requires an explicit local configuration and confirmation. Review configuration and test in paper/demo mode before enabling real-money execution.

## Reporting

If you find a security issue, do not include credentials, account identifiers, or private trading information in a public issue.
