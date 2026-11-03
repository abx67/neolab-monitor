"""Email notification for job updates."""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

from src.config import Config
from src.scraper.models import Job


class EmailNotifier:
    """Send formatted HTML email with job listings and change highlights."""

    def __init__(self, config: Config):
        self.config = config

    def send(
        self,
        all_jobs: Dict[str, List[Job]],
        new_jobs: Optional[Dict[str, List[Job]]] = None,
        removed_jobs: Optional[Dict[str, List[Job]]] = None,
        report_url: Optional[str] = None,
    ) -> bool:
        if not self.config.email_configured:
            print("  Email configuration incomplete — skipping notification.")
            return False

        sender_email = self.config.sender_email or ""
        sender_password = self.config.sender_password or ""
        recipient_email = self.config.recipient_email or ""

        total_jobs = sum(len(jobs) for jobs in all_jobs.values())
        total_new = sum(len(jobs) for jobs in (new_jobs or {}).values())
        total_removed = sum(len(jobs) for jobs in (removed_jobs or {}).values())

        subject_parts = [f"AI Research Jobs — {total_jobs} positions"]
        if total_new:
            subject_parts.append(f"({total_new} new!)")
        if total_removed:
            subject_parts.append(f"({total_removed} removed)")
        if not total_new and not total_removed:
            subject_parts.append("(no changes)")
        subject = " ".join(subject_parts)

        html = self._build_html(all_jobs, new_jobs or {}, removed_jobs or {}, report_url)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            print(f"  Email sent to {recipient_email}")
            return True
        except Exception as e:
            print(f"  Failed to send email: {e}")
            return False

    def _build_html(
        self,
        all_jobs: Dict[str, List[Job]],
        new_jobs: Dict[str, List[Job]],
        removed_jobs: Dict[str, List[Job]],
        report_url: Optional[str] = None,
    ) -> str:
        total_jobs = sum(len(jobs) for jobs in all_jobs.values())
        total_new = sum(len(jobs) for jobs in new_jobs.values())
        total_removed = sum(len(jobs) for jobs in removed_jobs.values())
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto;">
            <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db;">
                AI Research Engineer Jobs Update
            </h2>
            <p style="color: #7f8c8d;">
                <strong>Date:</strong> {date_str}<br>
                <strong>Total Positions:</strong> {total_jobs}
        """
        if total_new:
            body += f"<br><strong>New Positions:</strong> {total_new}"
        if total_removed:
            body += f"<br><strong>Removed Positions:</strong> {total_removed}"
        body += "</p>"

        # New jobs section
        if total_new:
            body += '<div style="background-color: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">'
            body += f'<h3 style="color: #27ae60; margin-top: 0;">🆕 New Jobs ({total_new})</h3>'
            for company, jobs in new_jobs.items():
                if not jobs:
                    continue
                body += f'<h4 style="color: #2c3e50; margin: 15px 0 10px 0;">🏢 {company}</h4>'
                for job in jobs:
                    body += self._job_card_html(job, border_color="#27ae60")
            body += "</div>"

        # Removed jobs section
        if total_removed:
            body += '<div style="background-color: #fdecea; padding: 15px; border-radius: 5px; margin: 20px 0;">'
            body += f'<h3 style="color: #c0392b; margin-top: 0;">Removed Jobs ({total_removed})</h3>'
            for company, jobs in removed_jobs.items():
                if not jobs:
                    continue
                body += f'<h4 style="color: #2c3e50; margin: 15px 0 10px 0;">🏢 {company}</h4>'
                for job in jobs:
                    body += f"""
                    <div style="background-color: #ffffff; padding: 10px; margin: 10px 0; border-radius: 3px; border-left: 4px solid #c0392b;">
                        <h5 style="color: #2c3e50; margin: 0 0 5px 0;">{job.title}</h5>
                        <p style="margin: 5px 0; color: #7f8c8d;">📍 {job.location}</p>
                        <span style="color: #c0392b;">This role no longer appears on the board.</span>
                    </div>
                    """
            body += "</div>"

        # No-changes notice (email is always sent, including unchanged runs)
        if not total_new and not total_removed:
            body += """<div style="background-color: #eef6fc; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #3498db;">"""
            body += '<h3 style="color: #2c3e50; margin-top: 0;">✅ No changes</h3>'
            body += f'<p style="margin: 5px 0; color: #7f8c8d;">No new or removed positions since the last check — {total_jobs} positions are being tracked.</p>'
            body += "</div>"

        # Optional link to the latest live GitHub report
        if report_url:
            body += f'<p style="margin: 20px 0;"><a href="{report_url}" style="color: #3498db; font-weight: bold;">📊 View the full live report on GitHub →</a></p>'

        body += f"""
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #bdc3c7;">
            <p style="color: #95a5a6; font-size: 12px; text-align: center;">
                Auto-generated by AI Jobs Scraper<br>
                Monitoring: Anthropic • OpenAI • DeepMind • X.ai • ByteDance Seed • Thinking Machines
            </p>
        </body>
        </html>
        """
        return body

    def _job_card_html(self, job: Job, border_color: str, index: int = 0,
                       indicator: str = "") -> str:
        num = f"{index}. " if index else ""
        apply = f'<a href="{job.apply_link}" style="color: #3498db; text-decoration: none; font-weight: bold;">Apply Now</a>' if job.apply_link else ""
        return f"""
        <div style="background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid {border_color};">
            <h5 style="color: #2c3e50; margin: 0 0 8px 0;">{num}{job.title}{indicator}</h5>
            <p style="margin: 5px 0; color: #7f8c8d;">📍 Location: {job.location}</p>
            {apply}
        </div>
        """
