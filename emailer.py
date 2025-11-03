# project_root/emailer.py
import smtplib
from email.message import EmailMessage
import logging

logger = logging.getLogger("emailer")

class Emailer:
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str, mail_from: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.mail_from = mail_from

    def send_email(self, to_addr: str, subject: str, body: str):
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.mail_from
        msg["To"] = to_addr
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            logger.info("Email sent to %s", to_addr)
        except Exception as e:
            logger.exception("Failed to send email to %s: %s", to_addr, str(e))
