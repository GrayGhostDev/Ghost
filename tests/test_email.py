"""Tests for src/ghost/email.py"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.ghost.email import (
    EmailMessage,
    EmailTemplate,
    EmailTemplates,
    SendGridProvider,
    SMTPProvider,
)


# ──────────────────────────────────────────────
# EmailMessage
# ──────────────────────────────────────────────

class TestEmailMessage:
    def test_to_string_normalized(self):
        msg = EmailMessage(to="a@b.com", subject="Hi")
        assert msg.to == ["a@b.com"]

    def test_to_list_unchanged(self):
        msg = EmailMessage(to=["a@b.com", "c@d.com"], subject="Hi")
        assert msg.to == ["a@b.com", "c@d.com"]

    def test_cc_normalized(self):
        msg = EmailMessage(to="a@b.com", subject="Hi", cc="cc@b.com")
        assert msg.cc == ["cc@b.com"]

    def test_bcc_normalized(self):
        msg = EmailMessage(to="a@b.com", subject="Hi", bcc="bcc@b.com")
        assert msg.bcc == ["bcc@b.com"]

    def test_defaults(self):
        msg = EmailMessage(to="a@b.com", subject="Hi")
        assert msg.body == ""
        assert msg.html_body is None
        assert msg.attachments == []
        assert msg.headers == {}
        assert msg.tags == []
        assert msg.metadata == {}


# ──────────────────────────────────────────────
# EmailTemplate
# ──────────────────────────────────────────────

class TestEmailTemplate:
    def test_render_string(self):
        tpl = EmailTemplate()
        result = tpl.render_string("Hello {{ name }}!", {"name": "Alice"})
        assert result == "Hello Alice!"

    def test_render_fallback_no_dir(self):
        tpl = EmailTemplate(template_dir="/nonexistent")
        result = tpl.render("Hello {{ x }}", {"x": "world"})
        assert result == "Hello world"

    def test_render_from_file(self, tmp_path):
        tpl_dir = tmp_path / "emails"
        tpl_dir.mkdir()
        (tpl_dir / "welcome.html").write_text("<p>Hi {{ name }}</p>")

        tpl = EmailTemplate(template_dir=str(tpl_dir))
        result = tpl.render("welcome.html", {"name": "Bob"})
        assert "<p>Hi Bob</p>" in result


# ──────────────────────────────────────────────
# EmailTemplates (built-in strings)
# ──────────────────────────────────────────────

class TestEmailTemplates:
    def test_welcome_template(self):
        from jinja2 import Template
        t = Template(EmailTemplates.WELCOME)
        result = t.render(name="User", app_name="Ghost", activation_link="https://x.com/activate")
        assert "User" in result
        assert "Ghost" in result

    def test_reset_template(self):
        from jinja2 import Template
        t = Template(EmailTemplates.RESET_EMAIL_TEMPLATE)
        result = t.render(name="User", reset_link="https://x.com/reset", expiry_hours=1)
        assert "reset" in result.lower()
        assert "1" in result

    def test_notification_template(self):
        from jinja2 import Template
        t = Template(EmailTemplates.NOTIFICATION)
        result = t.render(title="Alert", message="Something happened", action_link="https://x.com")
        assert "Alert" in result
        assert "Something happened" in result


# ──────────────────────────────────────────────
# SMTPProvider (mocked)
# ──────────────────────────────────────────────

class TestSMTPProvider:
    def test_send_plain(self):
        provider = SMTPProvider(host="smtp.test", port=587, username="u", password="p")
        msg = EmailMessage(to="a@b.com", subject="Hi", body="Hello")

        with patch("smtplib.SMTP") as MockSMTP:
            instance = MockSMTP.return_value
            result = provider.send(msg)
            assert result is True
            instance.starttls.assert_called_once()
            instance.login.assert_called_once_with("u", "p")
            instance.send_message.assert_called_once()
            instance.quit.assert_called_once()

    def test_send_html(self):
        provider = SMTPProvider(host="smtp.test", port=587)
        msg = EmailMessage(to="a@b.com", subject="Hi", body="txt", html_body="<b>html</b>")

        with patch("smtplib.SMTP") as MockSMTP:
            result = provider.send(msg)
            assert result is True

    def test_send_ssl(self):
        provider = SMTPProvider(host="smtp.test", port=465, use_ssl=True, use_tls=False)
        msg = EmailMessage(to="a@b.com", subject="Hi", body="Hello")

        with patch("smtplib.SMTP_SSL") as MockSMTPSSL:
            result = provider.send(msg)
            assert result is True

    def test_send_failure(self):
        provider = SMTPProvider(host="smtp.test", port=587)
        msg = EmailMessage(to="a@b.com", subject="Hi", body="Hello")

        with patch("smtplib.SMTP", side_effect=Exception("conn refused")):
            result = provider.send(msg)
            assert result is False

    def test_send_with_cc_bcc(self):
        provider = SMTPProvider(host="smtp.test", port=587)
        msg = EmailMessage(
            to="a@b.com", subject="Hi", body="Hello",
            cc=["cc@b.com"], bcc=["bcc@b.com"], reply_to="r@b.com",
        )
        with patch("smtplib.SMTP") as MockSMTP:
            result = provider.send(msg)
            assert result is True


# ──────────────────────────────────────────────
# SendGridProvider (mocked)
# ──────────────────────────────────────────────

class TestSendGridProvider:
    def test_build_payload(self):
        provider = SendGridProvider(api_key="sg-key")
        msg = EmailMessage(
            to="a@b.com", subject="Hi", body="text",
            html_body="<b>html</b>", from_email="from@b.com",
            from_name="Sender", reply_to="r@b.com",
            cc=["cc@b.com"], bcc=["bcc@b.com"],
        )
        payload = provider._build_payload(msg)

        assert payload["subject"] == "Hi"
        assert payload["from"]["email"] == "from@b.com"
        assert payload["from"]["name"] == "Sender"
        assert payload["reply_to"]["email"] == "r@b.com"
        assert len(payload["content"]) == 2
        assert payload["personalizations"][0]["cc"][0]["email"] == "cc@b.com"
        assert payload["personalizations"][0]["bcc"][0]["email"] == "bcc@b.com"

    def test_send_success(self):
        provider = SendGridProvider(api_key="sg-key")
        msg = EmailMessage(to="a@b.com", subject="Hi", body="text")

        mock_response = MagicMock()
        mock_response.status_code = 202

        with patch("httpx.post", return_value=mock_response):
            assert provider.send(msg) is True

    def test_send_failure_status(self):
        provider = SendGridProvider(api_key="sg-key")
        msg = EmailMessage(to="a@b.com", subject="Hi", body="text")

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        with patch("httpx.post", return_value=mock_response):
            assert provider.send(msg) is False

    def test_send_exception(self):
        provider = SendGridProvider(api_key="sg-key")
        msg = EmailMessage(to="a@b.com", subject="Hi", body="text")

        with patch("httpx.post", side_effect=Exception("network error")):
            assert provider.send(msg) is False

    @pytest.mark.asyncio
    async def test_send_async_success(self):
        provider = SendGridProvider(api_key="sg-key")
        msg = EmailMessage(to="a@b.com", subject="Hi", body="text")

        mock_response = MagicMock()
        mock_response.status_code = 202

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            assert await provider.send_async(msg) is True
