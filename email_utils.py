import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

def send_lead_email(lead):
    try:
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASSWORD")
        mail_from = os.getenv("MAIL_FROM", smtp_user)
        sales_emails = os.getenv("SALES_EMAILS", "")
        recipient_list = [email.strip() for email in sales_emails.split(",") if email.strip()]

        if not recipient_list:
            print("❌ No recipient emails found. Aborting.")
            return

        msg = MIMEMultipart()
        msg['From'] = mail_from
        msg['To'] = ", ".join(recipient_list)
        msg['Subject'] = f"Voicebot Lead: {lead.get('call_id') or 'Unknown Call ID'}"

        body_text = f"""
        New lead received from Voicebot.

        Call ID: {lead.get('call_id') or 'N/A'}
        Customer Name: {lead.get('first_name','')} {lead.get('last_name','')}
        Phone: {lead.get('phone','N/A')}
        Email: {lead.get('email','N/A')}
        Plan: {lead.get('plan','N/A')}
        Consent: {lead.get('consent','N/A')}
        """
        msg.attach(MIMEText(body_text, 'plain'))

        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        print("✅ Email sent successfully to:", ", ".join(recipient_list))

    except Exception as e:
        print(f"❌ Email sending failed: {e}")
