"""
S&P 500 Automated Analysis Scheduler
Analyzes top S&P 500 stocks every 20 minutes
Sends human-readable recommendations
"""

import asyncio
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from mcp_stock_agent import MCPStockAgent
from notification_manager import NotificationManager
import logging

logger = logging.getLogger(__name__)

# Top 50 S&P 500 stocks (you can expand to all 500)
SP500_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM',
    'JNJ', 'V', 'WMT', 'BAC', 'DIS', 'VZ', 'CSCO', 'INTC', 'AMD',
    'NFLX', 'PYPL', 'SQ', 'UBER', 'LYFT', 'SNAP', 'ZM', 'DDOG',
    'OKTA', 'CRWD', 'MDB', 'SPLK', 'SNOW', 'CRM', 'ADBE', 'AVGO',
    'QCOM', 'AMAT', 'ASML', 'LRCX', 'SNPS', 'CDNS', 'VEEV', 'ESTC',
    'PSTG', 'DELL', 'HPE', 'FTNT', 'ZS', 'NET', 'DOCN', 'RIOT',
    'MARA', 'COIN', 'HOOD', 'DASH'
]

class SP500Scheduler:
    def __init__(self):
        self.agent = MCPStockAgent()
        self.notifier = NotificationManager()
        self.scheduler = BackgroundScheduler()
        self.buy_opportunities = []
        
    def format_recommendation(self, analysis_results):
        """Format analysis results as human-readable recommendations"""
        if not analysis_results:
            return "No buy opportunities found in this analysis cycle."
        
        # Sort by buy score (highest first)
        sorted_results = sorted(analysis_results, key=lambda x: x.buy_score, reverse=True)
        
        # Create human-readable message
        message = "📊 S&P 500 ANALYSIS REPORT\n"
        message += f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += "=" * 50 + "\n\n"
        
        message += f"🎯 TOP BUY RECOMMENDATIONS ({len(sorted_results)} stocks)\n"
        message += "-" * 50 + "\n\n"
        
        for i, result in enumerate(sorted_results[:10], 1):  # Top 10
            signal_emoji = "🔴" if result.buy_signal == "STRONG_BUY" else "🟠" if result.buy_signal == "BUY" else "🟡"
            
            message += f"{i}. {signal_emoji} {result.ticker}\n"
            message += f"   Buy Score: {result.buy_score:.0%}\n"
            message += f"   Signal: {result.buy_signal}\n"
            message += f"   Thesis: {result.thesis}\n"
            message += f"   Key Factors: {', '.join(result.key_factors[:3])}\n"
            message += f"   Confidence: {result.confidence}\n"
            if result.targets:
                message += f"   Targets - Up: ${result.targets.get('upside', 'N/A')} / Down: ${result.targets.get('downside', 'N/A')}\n"
            message += "\n"
        
        message += "=" * 50 + "\n"
        message += f"Total Analyzed: {len(analysis_results)}\n"
        message += f"Buy Score >= 0.70: {len([r for r in analysis_results if r.buy_score >= 0.70])}\n"
        message += "=" * 50 + "\n"
        
        return message
    
    async def analyze_sp500(self):
        """Analyze all S&P 500 tickers"""
        logger.info(f"Starting S&P 500 analysis of {len(SP500_TICKERS)} stocks...")
        
        results = []
        errors = []
        
        for ticker in SP500_TICKERS:
            try:
                # Mock price (in real scenario, fetch from API)
                price = 100  # Default price for analysis
                
                # Analyze ticker
                analysis = await self.agent.analyze_ticker(ticker, price)
                results.append(analysis)
                
                logger.info(f"✓ {ticker}: {analysis.buy_score:.0%} - {analysis.buy_signal}")
                
            except Exception as e:
                logger.error(f"✗ {ticker}: {str(e)}")
                errors.append((ticker, str(e)))
        
        # Filter buy opportunities (score >= 0.70)
        self.buy_opportunities = [r for r in results if r.buy_score >= 0.70]
        
        logger.info(f"Analysis complete: {len(results)} analyzed, {len(self.buy_opportunities)} buy opportunities found")
        
        return results
    
    async def send_recommendations(self):
        """Send recommendations to users"""
        if not self.buy_opportunities:
            logger.info("No buy opportunities found")
            return
        
        message = self.format_recommendation(self.buy_opportunities)
        
        logger.info("Sending recommendations via Slack and Email...")
        
        # Send via Slack
        try:
            result = await self.notifier.send_notification(
                ticker="SP500",
                analysis=self.buy_opportunities[0],
                channels=["slack"],
                message=message
            )
            logger.info(f"Slack notification sent: {result}")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
        
        # Send via Email
        try:
            result = await self.notifier.send_notification(
                ticker="SP500",
                analysis=self.buy_opportunities[0],
                channels=["email"],
                message=message
            )
            logger.info(f"Email notification sent: {result}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    def scheduled_analysis(self):
        """Scheduled task - analyze S&P 500 every 20 minutes"""
        logger.info("Running scheduled S&P 500 analysis...")
        
        # Run async analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(self.analyze_sp500())
            
            # Send recommendations
            loop.run_until_complete(self.send_recommendations())
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
        finally:
            loop.close()
    
    def start(self):
        """Start the scheduler"""
        logger.info("Starting S&P 500 scheduler (every 20 minutes)...")
        
        # Schedule analysis every 20 minutes
        self.scheduler.add_job(
            self.scheduled_analysis,
            IntervalTrigger(minutes=20),
            id='sp500_analysis',
            name='S&P 500 Analysis',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Scheduler started!")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")


# Global scheduler instance
sp500_scheduler = None

def init_sp500_scheduler():
    """Initialize S&P 500 scheduler"""
    global sp500_scheduler
    sp500_scheduler = SP500Scheduler()
    sp500_scheduler.start()
    return sp500_scheduler

def stop_sp500_scheduler():
    """Stop S&P 500 scheduler"""
    global sp500_scheduler
    if sp500_scheduler:
        sp500_scheduler.stop()
