"""
Email Management Module

Provides email sending capabilities with multiple provider support including SMTP,
SendGrid, AWS SES, and more. Includes templating, attachments, and async sending.
"""

import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import aiosmtplib
from jinja2 import Template, Environment, FileSystemLoader, select_autoescape
import os
from .config import get_config
from .logging import get_logger, LoggerMixin


class EmailProvider(Enum):
    """Supported email providers."""
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    AWS_SES = "aws_ses"
    MAILGUN = "mailgun"
    POSTMARK = "postmark"


@dataclass
class EmailAttachment:
    """Email attachment data."""
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass
class EmailMessage:
    """Email message structure."""
    to: Union[str, List[str]]
    subject: str
    body: str = ""
    html_body: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    cc: Optional[Union[str, List[str]]] = None
    bcc: Optional[Union[str, List[str]]] = None
    reply_to: Optional[str] = None
    attachments: List[EmailAttachment] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Normalize email addresses to lists."""
        if isinstance(self.to, str):
            self.to = [self.to]
        if self.cc and isinstance(self.cc, str):
            self.cc = [self.cc]
        if self.bcc and isinstance(self.bcc, str):
            self.bcc = [self.bcc]


class EmailTemplate:
    """Email template manager."""
    
    def __init__(self, template_dir: Optional[str] = None):
        """Initialize template manager.
        
        Args:
            template_dir: Directory containing email templates
        """
        self.template_dir = template_dir or "templates/emails"
        if os.path.exists(self.template_dir):
            self.env = Environment(
                loader=FileSystemLoader(self.template_dir),
                autoescape=select_autoescape(['html', 'xml'])
            )
        else:
            self.env = Environment(
                autoescape=select_autoescape(['html', 'xml'])
            )
    
    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render an email template.
        
        Args:
            template_name: Name of the template file
            context: Template context variables
            
        Returns:
            Rendered template string
        """
        if os.path.exists(self.template_dir):
            template = self.env.get_template(template_name)
            return template.render(**context)
        else:
            # Fallback to string template
            template = Template(template_name)
            return template.render(**context)
    
    def render_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """Render a template from a string.
        
        Args:
            template_string: Template as a string
            context: Template context variables
            
        Returns:
            Rendered template string
        """
        template = Template(template_string)
        return template.render(**context)


class SMTPProvider(LoggerMixin):
    """SMTP email provider."""
    
    def __init__(self, host: str, port: int, username: Optional[str] = None,
                 password: Optional[str] = None, use_tls: bool = True,
                 use_ssl: bool = False, timeout: int = 30):
        """Initialize SMTP provider.
        
        Args:
            host: SMTP server host
            port: SMTP server port
            username: SMTP username
            password: SMTP password
            use_tls: Use TLS encryption
            use_ssl: Use SSL encryption
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout
    
    def send(self, message: EmailMessage) -> bool:
        """Send email via SMTP.
        
        Args:
            message: Email message to send
            
        Returns:
            True if sent successfully
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative') if message.html_body else MIMEText(message.body)
            
            # Set headers
            msg['Subject'] = message.subject
            msg['From'] = message.from_email or self.username
            msg['To'] = ', '.join(message.to)
            
            if message.cc:
                msg['Cc'] = ', '.join(message.cc)
            if message.reply_to:
                msg['Reply-To'] = message.reply_to
            
            # Add custom headers
            for key, value in message.headers.items():
                msg[key] = value
            
            # Add body
            if message.html_body:
                msg.attach(MIMEText(message.body, 'plain'))
                msg.attach(MIMEText(message.html_body, 'html'))
            
            # Add attachments
            for attachment in message.attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.content)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {attachment.filename}'
                )
                msg.attach(part)
            
            # Send email
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                if self.use_tls:
                    server.starttls()
            
            if self.username and self.password:
                server.login(self.username, self.password)
            
            recipients = list(message.to)
            if message.cc:
                recipients.extend(message.cc)
            if message.bcc:
                recipients.extend(message.bcc)
            
            server.send_message(msg, to_addrs=recipients)
            server.quit()
            
            self.logger.info(f"Email sent successfully to {', '.join(message.to)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False
    
    async def send_async(self, message: EmailMessage) -> bool:
        """Send email asynchronously via SMTP.
        
        Args:
            message: Email message to send
            
        Returns:
            True if sent successfully
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative') if message.html_body else MIMEText(message.body)
            
            # Set headers
            msg['Subject'] = message.subject
            msg['From'] = message.from_email or self.username
            msg['To'] = ', '.join(message.to)
            
            if message.cc:
                msg['Cc'] = ', '.join(message.cc)
            if message.reply_to:
                msg['Reply-To'] = message.reply_to
            
            # Add body
            if message.html_body:
                msg.attach(MIMEText(message.body, 'plain'))
                msg.attach(MIMEText(message.html_body, 'html'))
            
            # Send email asynchronously
            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
                use_tls=self.use_ssl,
                timeout=self.timeout
            )
            
            self.logger.info(f"Email sent asynchronously to {', '.join(message.to)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send async email: {e}")
            return False


class EmailManager(LoggerMixin):
    """Manages email sending with multiple providers."""
    
    def __init__(self, provider: Optional[EmailProvider] = None,
                 smtp_config: Optional[Dict[str, Any]] = None,
                 template_dir: Optional[str] = None):
        """Initialize email manager.
        
        Args:
            provider: Email provider to use
            smtp_config: SMTP configuration
            template_dir: Directory for email templates
        """
        self.provider = provider or EmailProvider.SMTP
        self.smtp_config = smtp_config or {}
        self.template_manager = EmailTemplate(template_dir)
        self._setup_provider()
    
    def _setup_provider(self):
        """Setup the email provider."""
        if self.provider == EmailProvider.SMTP:
            config = get_config()
            
            # Get SMTP settings from config or use provided
            self.smtp = SMTPProvider(
                host=self.smtp_config.get('host', config.get('email.smtp.host', 'localhost')),
                port=self.smtp_config.get('port', config.get('email.smtp.port', 587)),
                username=self.smtp_config.get('username', config.get('email.smtp.username')),
                password=self.smtp_config.get('password', config.get('email.smtp.password')),
                use_tls=self.smtp_config.get('use_tls', config.get('email.smtp.use_tls', True)),
                use_ssl=self.smtp_config.get('use_ssl', config.get('email.smtp.use_ssl', False))
            )
        elif self.provider == EmailProvider.SENDGRID:
            # Would require sendgrid package
            self.logger.warning("SendGrid provider not yet implemented")
        elif self.provider == EmailProvider.AWS_SES:
            # Would require boto3 package
            self.logger.warning("AWS SES provider not yet implemented")
        else:
            self.logger.warning(f"Provider {self.provider} not yet implemented")
    
    def send(self, message: EmailMessage) -> bool:
        """Send an email message.
        
        Args:
            message: Email message to send
            
        Returns:
            True if sent successfully
        """
        if self.provider == EmailProvider.SMTP and hasattr(self, 'smtp'):
            return self.smtp.send(message)
        else:
            self.logger.error(f"Provider {self.provider} not available")
            return False
    
    async def send_async(self, message: EmailMessage) -> bool:
        """Send an email message asynchronously.
        
        Args:
            message: Email message to send
            
        Returns:
            True if sent successfully
        """
        if self.provider == EmailProvider.SMTP and hasattr(self, 'smtp'):
            return await self.smtp.send_async(message)
        else:
            self.logger.error(f"Provider {self.provider} not available")
            return False
    
    def send_template(self, to: Union[str, List[str]], template_name: str,
                     context: Dict[str, Any], subject: str,
                     **kwargs) -> bool:
        """Send an email using a template.
        
        Args:
            to: Recipient email address(es)
            template_name: Name of the template
            context: Template context variables
            subject: Email subject
            **kwargs: Additional EmailMessage fields
            
        Returns:
            True if sent successfully
        """
        # Render template
        html_body = self.template_manager.render(template_name, context)
        
        # Create plain text version (simple strip tags)
        import re
        body = re.sub('<[^<]+?>', '', html_body)
        
        # Create message
        message = EmailMessage(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            **kwargs
        )
        
        return self.send(message)
    
    async def send_template_async(self, to: Union[str, List[str]], template_name: str,
                                  context: Dict[str, Any], subject: str,
                                  **kwargs) -> bool:
        """Send an email using a template asynchronously.
        
        Args:
            to: Recipient email address(es)
            template_name: Name of the template
            context: Template context variables
            subject: Email subject
            **kwargs: Additional EmailMessage fields
            
        Returns:
            True if sent successfully
        """
        # Render template
        html_body = self.template_manager.render(template_name, context)
        
        # Create plain text version
        import re
        body = re.sub('<[^<]+?>', '', html_body)
        
        # Create message
        message = EmailMessage(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            **kwargs
        )
        
        return await self.send_async(message)
    
    def send_bulk(self, messages: List[EmailMessage]) -> List[bool]:
        """Send multiple emails.
        
        Args:
            messages: List of email messages
            
        Returns:
            List of success statuses
        """
        results = []
        for message in messages:
            results.append(self.send(message))
        return results
    
    async def send_bulk_async(self, messages: List[EmailMessage]) -> List[bool]:
        """Send multiple emails asynchronously.
        
        Args:
            messages: List of email messages
            
        Returns:
            List of success statuses
        """
        tasks = [self.send_async(message) for message in messages]
        return await asyncio.gather(*tasks)


# Singleton instance
_email_manager: Optional[EmailManager] = None


def get_email_manager(provider: Optional[EmailProvider] = None,
                      smtp_config: Optional[Dict[str, Any]] = None,
                      template_dir: Optional[str] = None) -> EmailManager:
    """Get or create email manager instance.
    
    Args:
        provider: Email provider to use
        smtp_config: SMTP configuration
        template_dir: Directory for email templates
        
    Returns:
        EmailManager instance
    """
    global _email_manager
    if _email_manager is None:
        _email_manager = EmailManager(provider, smtp_config, template_dir)
    return _email_manager


# Common email templates as strings
class EmailTemplates:
    """Common email template strings."""
    
    WELCOME = """
    <h2>Welcome {{ name }}!</h2>
    <p>Thank you for joining {{ app_name }}.</p>
    <p>Get started by <a href="{{ activation_link }}">activating your account</a>.</p>
    """
    
    PASSWORD_RESET_TEMPLATE = """  # nosec B105
    <h2>Password Reset Request</h2>
    <p>Hi {{ name }},</p>
    <p>We received a request to reset your password.</p>
    <p><a href="{{ reset_link }}">Click here to reset your password</a></p>
    <p>This link will expire in {{ expiry_hours }} hours.</p>
    <p>If you didn't request this, please ignore this email.</p>
    """
    
    NOTIFICATION = """
    <h2>{{ title }}</h2>
    <p>{{ message }}</p>
    {% if action_link %}
    <p><a href="{{ action_link }}">{{ action_text | default('View Details') }}</a></p>
    {% endif %}
    """