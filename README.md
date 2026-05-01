# 微信公众号批量改写系统

Single-user web tool that crawls WeChat 公众号 article URLs into a library, batch-rewrites them with configurable LLMs, runs 4-dimension AI review, and pushes drafts to WeChat draft boxes for multiple managed accounts.

## Quick start

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
docker compose run --rm api python -m app.scripts.init_admin --password yourpass
# Append printed hash into .env as ADMIN_PASSWORD_HASH=<hash>
# Set JWT_SECRET to a long random string in .env
docker compose up -d --build
```

Open http://localhost — log in with `admin` + `yourpass`.

## First-run configuration

1. Settings → add an AI Provider (e.g. DeepSeek, base_url `https://api.deepseek.com/v1`).
2. Settings → bind roles writer / reviewer / lite to provider+model.
3. Accounts → add a 公众号: name, AppID, AppSecret, category, prompts. Requires authenticated 服务号 / 订阅号 for the draft API.
4. Library → paste WeChat article URLs and tag them.
5. Library → select items + target account → click 改写.
6. Drafts → wait for status `reviewed`, open detail, edit, set cover, click 推送到微信.

## Architecture

See `docs/superpowers/specs/2026-04-30-wechat-batch-rewrite-design.md`.

## Development

Backend:

```bash
cd backend
uv venv && uv pip install -e ".[dev]"
uv run pytest -v
uv run ruff check .
```

Frontend:

```bash
cd frontend
pnpm install
pnpm dev
pnpm exec playwright test
```

## Backup

```bash
docker compose exec postgres pg_dump -U postgres wechat_rewriter > backup.sql
```

## Security notes

- Front the bundled `web` container with Caddy / nginx-proxy + Let's Encrypt for HTTPS.
- All AI keys and 公众号 secrets are encrypted with Fernet at rest. Losing `ENCRYPTION_KEY` makes them unrecoverable.

## v1 limitations

- WeChat article URLs only (no third-party scraping platform integration).
- No automatic publish — push to draft box only; final 发布 happens manually in 公众号 admin.
- No AI cover image generation.
- Single-user only.
