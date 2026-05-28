"""
Notification Manager

Sends buy signal notifications via multiple channels:
- Email
- Slack
- Discord
- Webhook
- Telegram (optional)
"""

import asyncio
import json
import logging
import smtplib
from datetime import datetime
from typing import Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiohttp

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages sending notifications via multiple channels"""

    def __init__(
        self,
        email_config: Optional[Dict] = None,
        slack_webhook: Optional[str] = None,
        discord_webhook: Optional[str] = None,
        custom_webhook: Optional[str] = None
    ):
        """Initialize notification manager"""
        self.email_config = email_config or {}
        self.slack_webhook = slack_webhook
        self.discord_webhook = discord_webhook
        self.custom_webhook = custom_webhook

    async def send_notification(
        self,
        ticker: str,
        analysis: Dict,
        channels: List[str] = None,
        recipients: List[str] = None
    ) -> Dict[str, bool]:
        """
        Send notification via specified channels

        Args:
            ticker: Stock ticker
            analysis: Analysis result
            channels: List of channels ('email', 'slack', 'discord', 'webhook')
            recipients: Email recipients

        Returns:
            Dict with success status for each channel
        """
        channels = channels or ["email"]
        results = {}

        for channel in channels:
            try:
                if channel == "email" and recipients:
                    results["email"] = await self._send_email(
                        ticker, analysis, recipients
                    )
                elif channel == "slack":
                    results["slack"] = await self._send_slack(ticker, analysis)
                elif channel == "discord":
                    results["discord"] = await self._send_discord(ticker, analysis)
                elif channel == "webhook":
                    results["webhook"] = await self._send_webhook(ticker, analysis)
            except Exception as e:
                logger.error(f"Error sending {channel} notification: {str(e)}")
                results[channel] = False

        return results

    async def _send_email(
        self,
        ticker: str,
        analysis: Dict,
        recipients: List[str]
    ) -> bool:
        """Send email notification"""
        try:
            # Create email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"BUY SIGNAL - {ticker} ({analysis['buy_score']:.0%})"
            msg['From'] = self.email_config.get('from_address', 'alerts@trading.com')

            # HTML body
            html_body = self._create_email_html(ticker, analysis)
            msg.attach(MIMEText(html_body, 'html'))

            # Send email (async wrapper)
            await asyncio.to_thread(
                self._send_smtp,
                msg,
                recipients
            )

            logger.info(f"Email sent to {recipients} for {ticker}")
            return True

        except Exception as e:
            logger.error(f"Email send failed: {str(e)}")
            return False

    def _send_smtp(self, msg, recipients):
        """Send via SMTP (blocking)"""
        smtp_server = self.email_config.get('smtp_server', 'smtp.gmail.com')
        smtp_port = self.email_config.get('smtp_port', 587)
        username = self.email_config.get('username')
        password = self.email_config.get('password')

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            if username and password:
                server.login(username, password)
            server.send_message(msg, to_addrs=recipients)

    def _create_email_html(self, ticker: str, analysis: Dict) -> str:
        """Create HTML email body"""
        buy_score_pct = f"{analysis['buy_score']:.0%}"
        signal = analysis.get('buy_signal', 'UNKNOWN')
        price = analysis['price']
        timestamp = analysis['timestamp']

        return f"""
        <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .header {{ background: #1a73e8; color: white; padding: 20px; text-align: center; }}
                    .section {{ margin: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                    .score {{ font-size: 32px; font-weight: bold; color: #1a73e8; }}
                    .signal {{ font-size: 24px; font-weight: bold; color: #34a853; }}
                    .risk {{ color: #ea4335; }}
                    .targets {{ background: #f1f3f4; padding: 10px; border-radius: 3px; margin: 10px 0; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #ddd; }}
                    th {{ background: #f1f3f4; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>STOCK ANALYSIS REPORT</h1>
                </div>

                <div class="section">
                    <h2>{ticker}</h2>
                    <div class="score">{buy_score_pct} Score</div>
                    <div class="signal">{signal}</div>
                    <p>Current Price: <strong>${price:.2f}</strong></p>
                    <p>Analysis Time: {timestamp}</p>
                </div>

                <div class="section">
                    <h3>Analysis Breakdown</h3>
                    <table>
                        <tr>
                            <th>Component</th>
                            <th>Score</th>
                        </tr>
                        <tr>
                            <td>Technical Analysis</td>
                            <td>{analysis.get('technical_score', 0):.0%}</td>
                        </tr>
                        <tr>
                            <td>Sentiment Analysis</td>
                            <td>{analysis.get('sentiment_score', 0):.0%}</td>
                        </tr>
                        <tr>
                            <td>ML Prediction</td>
                            <td>{analysis.get('ml_score', 0):.0%}</td>
                        </tr>
                        <tr>
                            <td>Strategy Score</td>
                            <td>{analysis.get('strategy_score', 0):.0%}</td>
                        </tr>
                        <tr>
                            <td>Market Environment</td>
                            <td>{analysis.get('market_score', 0):.0%}</td>
                        </tr>
                    </table>
                </div>

                <div class="section">
                    <h3>Investment Thesis</h3>
                    <p>{analysis.get('thesis', 'Analysis in progress...')}</p>
                </div>

                <div class="section">
                    <h3>Price Targets</h3>
                    <div class="targets">
                        <p><strong>Entry Price:</strong> ${analysis.get('price', 0):.2f}</p>
                        <p><strong>Stop Loss:</strong> ${analysis.get('stop_loss', 0):.2f}
                           <span class="risk">({analysis.get('stop_loss_pct', 0):.1f}%)</span></p>
                        <p><strong>Target 1:</strong> ${analysis.get('target_1', 0):.2f}
                           (+{analysis.get('target1_pct', 0):.1f}%)</p>
                        <p><strong>Target 2:</strong> ${analysis.get('target_2', 0):.2f}
                           (+{analysis.get('target2_pct', 0):.1f}%)</p>
                    </div>
                </div>

                <div class="section">
                    <h3>Risk Level: {analysis.get('risk_level', 'MODERATE')}</h3>
                    <p>Key Risks:</p>
                    <ul>
                        {"".join([f"<li>{risk}</li>" for risk in analysis.get('risks', [])])}
                    </ul>
                </div>

                <div class="section" style="text-align: center; color: #999; font-size: 12px;">
                    <p>This is an automated analysis. Always do your own research before investing.</p>
                    <p>Analysis ID: {analysis.get('analysis_id', 'N/A')}</p>
                </div>
            </body>
        </html>
        """

    async def _send_slack(self, ticker: str, analysis: Dict) -> bool:
        """Send Slack notification"""
        if not self.slack_webhook:
            logger.warning("Slack webhook not configured")
            return False

        try:
            message = {
                "text": f"📊 BUY SIGNAL: {ticker}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"📊 {ticker} - Buy Signal",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Buy Score:*\n{analysis['buy_score']:.0%} ✅"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Signal:*\n{analysis.get('buy_signal', 'N/A')}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Price:*\n${analysis['price']:.2f}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Risk:*\n{analysis.get('risk_level', 'N/A')}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Thesis:*\n{analysis.get('thesis', '')[:300]}..."
                        }
                    },
                    {
                        "type": "divider"
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook,
                    json=message
                ) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent for {ticker}")
                        return True
                    else:
                        logger.error(f"Slack API error: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Slack send failed: {str(e)}")
            return False

    async def _send_discord(self, ticker: str, analysis: Dict) -> bool:
        """Send Discord notification"""
        if not self.discord_webhook:
            logger.warning("Discord webhook not configured")
            return False

        try:
            embed = {
                "title": f"📊 {ticker} - Buy Signal",
                "description": analysis.get('thesis', '')[:300],
                "color": 3447003,  # Blue
                "fields": [
                    {
                        "name": "Buy Score",
                        "value": f"{analysis['buy_score']:.0%} ✅",
                        "inline": True
                    },
                    {
                        "name": "Signal",
                        "value": analysis.get('buy_signal', 'N/A'),
                        "inline": True
                    },
                    {
                        "name": "Current Price",
                        "value": f"${analysis['price']:.2f}",
                        "inline": True
                    },
                    {
                        "name": "Risk Level",
                        "value": analysis.get('risk_level', 'N/A'),
                        "inline": True
                    }
                ],
                "timestamp": datetime.utcnow().isoformat()
            }

            payload = {"embeds": [embed]}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.discord_webhook,
                    json=payload
                ) as response:
                    if response.status in [200, 204]:
                        logger.info(f"Discord notification sent for {ticker}")
                        return True
                    else:
                        logger.error(f"Discord API error: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Discord send failed: {str(e)}")
            return False

    async def _send_webhook(self, ticker: str, analysis: Dict) -> bool:
        """Send to custom webhook"""
        if not self.custom_webhook:
            logger.warning("Custom webhook not configured")
            return False

        try:
            payload = {
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
                "analysis": analysis,
                "source": "stock-analysis-agent"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.custom_webhook,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status in [200, 201]:
                        logger.info(f"Webhook notification sent for {ticker}")
                        return True
                    else:
                        logger.error(f"Webhook error: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Webhook send failed: {str(e)}")
            return False


class NotificationTemplate:
    """Email and message templates"""

    @staticmethod
    def buy_signal_email(ticker: str, analysis: Dict) -> str:
        """Buy signal email template"""
        return f"""
        Subject: BUY SIGNAL - {ticker} ({analysis['buy_score']:.0%})

        {ticker} Analysis Report
        ========================

        Buy Score: {analysis['buy_score']:.0%}
        Signal: {analysis.get('buy_signal', 'N/A')}
        Risk Level: {analysis.get('risk_level', 'N/A')}
        Current Price: ${analysis['price']:.2f}

        Thesis:
        {analysis.get('thesis', '')}

        Price Targets:
        Entry: ${analysis['price']:.2f}
        Stop Loss: ${analysis.get('stop_loss', 0):.2f}
        Target 1: ${analysis.get('target_1', 0):.2f}
        Target 2: ${analysis.get('target_2', 0):.2f}

        Key Risks:
        {chr(10).join(['- ' + risk for risk in analysis.get('risks', [])])}
        """

    @staticmethod
    def watchlist_alert_email(ticker: str, event: str, details: Dict) -> str:
        """Watchlist alert email template"""
        return f"""
        Subject: ALERT - {ticker} {event.upper()}

        Watchlist Alert for {ticker}
        =============================

        Event: {event}
        Details: {json.dumps(details, indent=2)}
        Time: {datetime.utcnow().isoformat()}
        """


async def test_notification_manager():
    """Test notification manager"""
    manager = NotificationManager(
        email_config={
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'from_address': 'test@example.com'
        },
        slack_webhook="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    )

    analysis = {
        'ticker': 'AAPL',
        'buy_score': 0.78,
        'buy_signal': 'STRONG_BUY',
        'price': 150.50,
        'risk_level': 'MODERATE',
        'thesis': 'AAPL is showing strong technical setup with bullish momentum',
        'risks': ['Market correction risk', 'Earnings volatility'],
        'timestamp': datetime.utcnow().isoformat(),
        'technical_score': 0.75,
        'sentiment_score': 0.70,
        'ml_score': 0.85,
        'strategy_score': 0.72,
        'market_score': 0.65
    }

    # Send notifications
    results = await manager.send_notification(
        ticker='AAPL',
        analysis=analysis,
        channels=['slack'],
        recipients=['user@example.com']
    )

    print(f"Notification Results: {results}")


if __name__ == "__main__":
    asyncio.run(test_notification_manager())
