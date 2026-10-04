# OUR SMALL CAN RISE — Render-ready package

This version is simplified for Android/GitHub upload: only `app.py` and `requirements.txt` are needed.

## Render settings
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Environment variable: `SECRET_KEY` = a long random secret

After deployment, open `/setup` once to create the admin password, then use `/admin/login`.

## Payment workflow
Members pay manually to the official M-Pesa number shown on the site and submit the transaction/reference number. The admin verifies or rejects the payment. No M-Pesa API credentials are stored here.

## Important
This MVP uses SQLite. For real long-term association records, move the database to persistent PostgreSQL before treating the deployment as production-critical.
