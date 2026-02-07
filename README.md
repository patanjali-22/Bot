# 🤖 Microsoft Job Alert Bot

This bot monitors the Microsoft Careers website for new **Software Engineer** job postings (sorted by newest) and sends you an email notification when new jobs are found.

It runs **every hour** automatically using **GitHub Actions** (Free Tier).

## 🚀 Features
- **Smart Scraping**: Uses Playwright to handle Microsoft's dynamic JavaScript site.
- **State Aware**: Remembers jobs it has already seen to avoid duplicate alerts.
- **Email Notifications**: Sends an HTML-formatted email with direct apply links.
- **Free Hosting**: Runs entirely on GitHub Actions with no server costs.

## 🛠️ Setup Instructions

### 1. Push to GitHub
If you haven't already, push this code to a **Public** GitHub repository:
```bash
git init
git add .
git commit -m "Initial commit"
# Create a new repo on GitHub.com named 'microsoft-job-alert'
git remote add origin https://github.com/YOUR_USERNAME/microsoft-job-alert.git
git push -u origin main
```

### 2. Configure Secrets
For the bot to send emails, you need to add your credentials as **Secrets** in your GitHub repository.

1. Go to your repo on GitHub: **Settings** > **Secrets and variables** > **Actions**.
2. Click **New repository secret**.
3. Add these 3 secrets:

| Name | Value | Description |
|------|-------|-------------|
| `EMAIL_ADDRESS` | `patanjali1410@gmail.com` | The Gmail account sending the emails. |
| `EMAIL_PASSWORD` | `YOUR_APP_PASSWORD` | **Important**: Use an [App Password](https://support.google.com/accounts/answer/185833?hl=en), NOT your login password. |
| `NOTIFY_EMAIL` | `upatanjali6@gmail.com` | The email address to receive notifications. |

> **Note on Password**: If you have 2-Factor Authentication enabled on Gmail (likely), you **must** generate an App Password. Go to [Google Account](https://myaccount.google.com/) > Security > 2-Step Verification > App passwords.

### 3. Verify It Works
1. Go to the **Actions** tab in your repo.
2. Select **Microsoft Job Checker** on the left.
3. Click **Run workflow** manually to test it.
4. Check your email! 📧

---

## 🏃‍♂️ Running Locally (Optional)
If you want to test on your own machine:

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Set environment variables (or hardcode them for testing):
   - Windows (PowerShell):
     ```powershell
     $env:EMAIL_ADDRESS="patanjali1410@gmail.com"
     $env:EMAIL_PASSWORD="your-app-password"
     $env:NOTIFY_EMAIL="upatanjali6@gmail.com"
     ```
3. Run the script:
   ```bash
   python src/main.py
   ```
