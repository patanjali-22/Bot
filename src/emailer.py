import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def send_email(new_jobs):
    """
    Sends an email notification with the list of new jobs.
    """
    sender_email = os.environ.get("EMAIL_ADDRESS")
    sender_password = os.environ.get("EMAIL_PASSWORD")
    receiver_email = os.environ.get("NOTIFY_EMAIL")

    if not all([sender_email, sender_password, receiver_email]):
        print("Missing email configuration. Skipping email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚀 {len(new_jobs)} New Microsoft Job(s) Found!"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    # HTML Body
    html_content = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; }
            .job-card { 
                border: 1px solid #ddd; 
                padding: 15px; 
                margin-bottom: 10px; 
                border-radius: 5px;
                background-color: #f9f9f9;
            }
            .job-title { color: #0078d4; font-size: 18px; font-weight: bold; }
            .job-location { color: #666; font-size: 14px; margin-top: 5px; }
            .apply-btn {
                display: inline-block;
                background-color: #0078d4;
                color: white;
                padding: 10px 15px;
                text-decoration: none;
                border-radius: 4px;
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <h2>New Job Postings match your criteria</h2>
    """

    for job in new_jobs:
        html_content += f"""
        <div class="job-card">
            <div class="job-title">{job.get('title', 'Unknown Role')}</div>
            <div class="job-location">📍 {job.get('location', 'Unknown Location')}</div>
            <a href="{job.get('link', '#')}" class="apply-btn">View Job</a>
        </div>
        """

    html_content += """
        <p style="font-size: 12px; color: #888;">
            This email was sent by your Microsoft Job Alert Bot.
        </p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print(f"Email sent successfully to {receiver_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
