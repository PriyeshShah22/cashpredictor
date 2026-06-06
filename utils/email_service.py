from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText


SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 465


def send_email(to_email: str, subject: str, message: str) -> dict:
    """Send an email using Gmail SMTP.

    Falls back to demo mode by printing the alert when credentials are not
    configured, so the project remains runnable in hackathon demos.
    """
    email_user = os.environ.get('EMAIL_USER')
    email_pass = os.environ.get('EMAIL_PASS')

    if not email_user or not email_pass:
        print('\n[CashForecast Demo Alert] SMTP credentials missing. Email not sent.')
        print(f'To: {to_email or "demo-user"}')
        print(f'Subject: {subject}')
        print(message)
        print('[End Demo Alert]\n')
        return {
            'status': 'demo_console',
            'message': 'SMTP credentials missing; alert printed to console instead.',
        }

    if not to_email:
        return {
            'status': 'skipped',
            'message': 'Recipient email is missing.',
        }

    mime_message = MIMEText(message, 'plain', 'utf-8')
    mime_message['Subject'] = subject
    mime_message['From'] = email_user
    mime_message['To'] = to_email

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, [to_email], mime_message.as_string())
        return {
            'status': 'sent',
            'message': f'Alert email sent to {to_email}.',
        }
    except Exception as exc:
        print('\n[CashForecast Email Error] Falling back to console output.')
        print(f'Error: {exc}')
        print(f'To: {to_email}')
        print(f'Subject: {subject}')
        print(message)
        print('[End Email Error Fallback]\n')
        return {
            'status': 'error_fallback',
            'message': str(exc),
        }
