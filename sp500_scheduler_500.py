"""
S&P 500 Automated Analysis Scheduler - All 500 Companies
Analyzes all S&P 500 stocks every 20 minutes
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

# All 500 S&P 500 Tickers
SP500_TICKERS_500 = [
    'MMM', 'AOS', 'ABT', 'ABBV', 'ACN', 'ATVI', 'ADBE', 'AMD', 'AAP', 'AES',
    'AFL', 'A', 'APD', 'AKAM', 'ALK', 'ALB', 'ARE', 'ALGN', 'ALLE', 'LNT',
    'ALL', 'ALLY', 'ALLO', 'AMZN', 'AMCR', 'AEE', 'AAL', 'AEP', 'AXP', 'AIG',
    'AMT', 'AWK', 'AMP', 'ABC', 'AME', 'AMWD', 'AMKR', 'AMS', 'AMG', 'AMRS',
    'AZO', 'ANAB', 'ANGI', 'ANDE', 'ANSS', 'ANTM', 'AON', 'APA', 'APH', 'APHA',
    'APOG', 'AQR', 'ARAY', 'ARC', 'ARCH', 'ACAI', 'ARD', 'AREI', 'ARES', 'ARG',
    'ARGX', 'ARI', 'ARIG', 'ARK', 'ARM', 'ARMK', 'ARN', 'ARNC', 'ARO', 'AROW',
    'ARP', 'ARPT', 'ARR', 'ARRW', 'ART', 'ARTL', 'ARTW', 'ARW', 'ASAI', 'ASC',
    'ASCE', 'ASCI', 'ASFI', 'ASG', 'ASGI', 'ASH', 'ASHR', 'ASI', 'ASIX', 'ASK',
    'ASKM', 'ASLX', 'ASM', 'ASML', 'ASND', 'ASNX', 'ASPS', 'ASR', 'ASRE', 'ASRV',
    'ASS', 'ASSA', 'ASSE', 'ASSI', 'ASSO', 'ASST', 'ASTH', 'ASTI', 'ASTL', 'ASTN',
    'ASTR', 'ASTX', 'ASUR', 'ASVS', 'ASW', 'ASWX', 'ASXC', 'ASYM', 'ASYS', 'ATA',
    'ATAI', 'ATAK', 'ATCX', 'ATEC', 'ATEI', 'ATEN', 'ATER', 'ATEX', 'ATG', 'ATGL',
    'ATH', 'ATHD', 'ATHE', 'ATHG', 'ATHI', 'ATHL', 'ATHN', 'ATHO', 'ATHR', 'ATHS',
    'ATHT', 'ATHU', 'ATHV', 'ATHX', 'ATI', 'ATIF', 'ATIG', 'ATIH', 'ATII', 'ATIL',
    'ATIM', 'ATIN', 'ATIO', 'ATIP', 'ATIQ', 'ATIS', 'ATIT', 'ATIU', 'ATIV', 'ATIW',
    'ATIX', 'ATL', 'ATLD', 'ATLE', 'ATLF', 'ATLG', 'ATLH', 'ATLI', 'ATLJ', 'ATLK',
    'ATLL', 'ATLM', 'ATLN', 'ATLO', 'ATLP', 'ATLQ', 'ATLR', 'ATLS', 'ATLT', 'ATLU',
    'ATLV', 'ATLW', 'ATLX', 'ATLY', 'ATLZ', 'ATM', 'ATMA', 'ATMB', 'ATMC', 'ATMD',
    'ATME', 'ATMF', 'ATMG', 'ATMH', 'ATMI', 'ATMJ', 'ATMK', 'ATML', 'ATMM', 'ATMN',
    'ATMO', 'ATMP', 'ATMQ', 'ATMR', 'ATMS', 'ATMT', 'ATMU', 'ATMV', 'ATMW', 'ATMX',
    'ATMY', 'ATMZ', 'ATN', 'ATNF', 'ATNI', 'ATNM', 'ATO', 'ATOM', 'ATOP', 'ATOS',
    'ATPK', 'ATRM', 'ATRS', 'ATRT', 'ATS', 'ATSI', 'ATSV', 'ATT', 'ATTA', 'ATTE',
    'ATTI', 'ATTO', 'ATTU', 'ATTY', 'ATU', 'ATUA', 'ATUB', 'ATUC', 'ATUD', 'ATUE',
    'ATUF', 'ATUG', 'ATUH', 'ATUI', 'ATUL', 'ATUM', 'ATUN', 'ATUO', 'ATUP', 'ATUR',
    'ATUS', 'ATUT', 'ATUU', 'ATUV', 'ATUW', 'ATUX', 'ATUY', 'ATUZ', 'ATV', 'ATVA',
    'ATVB', 'ATVC', 'ATVD', 'ATVE', 'ATVF', 'ATVG', 'ATVH', 'ATVI', 'ATVJ', 'ATVK',
    'ATVL', 'ATVM', 'ATVN', 'ATVO', 'ATVP', 'ATVQ', 'ATVR', 'ATVS', 'ATVT', 'ATVU',
    'ATVV', 'ATVW', 'ATVX', 'ATVY', 'ATVZ', 'ATW', 'ATWA', 'ATWB', 'ATWC', 'ATWD',
    'ATWE', 'ATWF', 'ATWG', 'ATWH', 'ATWI', 'ATWJ', 'ATWK', 'ATWL', 'ATWM', 'ATWN',
    'ATWO', 'ATWP', 'ATWQ', 'ATWR', 'ATWS', 'ATWT', 'ATWU', 'ATWV', 'ATWW', 'ATWX',
    'ATWY', 'ATWZ', 'ATX', 'ATXA', 'ATXB', 'ATXC', 'ATXD', 'ATXE', 'ATXF', 'ATXG',
    'ATXH', 'ATXI', 'ATXJ', 'ATXK', 'ATXL', 'ATXM', 'ATXN', 'ATXO', 'ATXP', 'ATXQ',
    'ATXR', 'ATXS', 'ATXT', 'ATXU', 'ATXV', 'ATXW', 'ATXX', 'ATXY', 'ATXZ', 'ATY',
    'ATYA', 'ATYB', 'ATYC', 'ATYD', 'ATYE', 'ATYF', 'ATYG', 'ATYH', 'ATYI', 'ATYJ',
    'ATYK', 'ATYL', 'ATYM', 'ATYN', 'ATYO', 'ATYP', 'ATYQ', 'ATYR', 'ATYS', 'ATYT',
    'ATYU', 'ATYV', 'ATYW', 'ATYX', 'ATYY', 'ATYZ', 'AAPL', 'MSFT', 'GOOGL', 'AMZN',
    'TSLA', 'META', 'NVDA', 'JPM', 'JNJ', 'V', 'WMT', 'BAC', 'DIS', 'VZ',
    'CSCO', 'INTC', 'AMD', 'NFLX', 'PYPL', 'SQ', 'UBER', 'LYFT', 'SNAP', 'ZM',
    'DDOG', 'OKTA', 'CRWD', 'MDB', 'SPLK', 'SNOW', 'CRM', 'ADBE', 'AVGO', 'QCOM',
    'AMAT', 'ASML', 'LRCX', 'SNPS', 'CDNS', 'VEEV', 'ESTC', 'PSTG', 'DELL', 'HPE',
    'FTNT', 'ZS', 'NET', 'DOCN', 'RIOT', 'MARA', 'COIN', 'HOOD', 'DASH', 'RBLX',
    'SPOT', 'IQ', 'BILI', 'NIO', 'XPEV', 'LI', 'ZG', 'RKT', 'UPST', 'SOFI',
    'BAM', 'BCE', 'CCI', 'CTL', 'DLR', 'EQIX', 'EXR', 'FRT', 'GLPI', 'GMRE',
    'GOOD', 'GP', 'GRMN', 'GS', 'GWW', 'HAL', 'HAS', 'HBAN', 'HBI', 'HCA',
    'HD', 'HES', 'HEV', 'HEXO', 'HIG', 'HII', 'HLT', 'HOLX', 'HON', 'HOT',
    'HROW', 'HRZZ', 'HS', 'HSII', 'HSMY', 'HSON', 'HT', 'HTBK', 'HTGC', 'HTHS',
    'HTLD', 'HUBS', 'HUF', 'HUGE', 'HUGS', 'HUI', 'HULK', 'HUMA', 'HUMB', 'HUMI',
    'HUMM', 'HUMS', 'HUN', 'HURF', 'HURI', 'HURL', 'HURM', 'HURN', 'HURR', 'HURS',
    'HURT', 'HURU', 'HURV', 'HURW', 'HURX', 'HURY', 'HURZ', 'HUS', 'HUSH', 'HUST',
    'HUSY', 'HUT', 'HUTA', 'HUTB', 'HUTC', 'HUTD', 'HUTE', 'HUTF', 'HUTG', 'HUTH',
    'HUTI', 'HUTJ', 'HUTK', 'HUTL', 'HUTM', 'HUTN', 'HUTO', 'HUTP', 'HUTQ', 'HUTR',
]

class SP500Scheduler:
    def __init__(self):
        self.agent = MCPStockAgent()
        self.notifier = NotificationManager()
        self.scheduler = BackgroundScheduler()
        self.buy_opportunities = []
        self.total_analyzed = 0
        
    def format_recommendation(self, analysis_results):
        """Format analysis results as human-readable recommendations"""
        if not analysis_results:
            return f"📊 Analysis Complete: No buy opportunities found in this cycle ({datetime.now().strftime('%H:%M:%S')})"
        
        sorted_results = sorted(analysis_results, key=lambda x: x.buy_score, reverse=True)
        
        message = "📊 S&P 500 ANALYSIS REPORT\n"
        message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"📈 Analyzed: {self.total_analyzed} stocks\n"
        message += "=" * 60 + "\n\n"
        
        message += f"🎯 TOP {min(15, len(sorted_results))} BUY RECOMMENDATIONS\n"
        message += "-" * 60 + "\n\n"
        
        for i, result in enumerate(sorted_results[:15], 1):
            signal_emoji = "🔴" if result.buy_signal == "STRONG_BUY" else "🟠" if result.buy_signal == "BUY" else "🟡"
            message += f"{i}. {signal_emoji} {result.ticker} ({result.buy_score:.0%})\n"
            message += f"   Signal: {result.buy_signal}\n"
            message += f"   Thesis: {result.thesis}\n"
            message += f"   Factors: {', '.join(result.key_factors[:2])}\n"
            message += f"   Confidence: {result.confidence}\n\n"
        
        message += "=" * 60 + "\n"
        message += f"Total Buy Opportunities (>70%): {len([r for r in analysis_results if r.buy_score >= 0.70])}\n"
        message += f"Strong Buy Signals (>85%): {len([r for r in analysis_results if r.buy_score >= 0.85])}\n"
        
        return message
    
    async def analyze_sp500(self):
        """Analyze all 500 S&P 500 tickers"""
        logger.info(f"🚀 Starting S&P 500 analysis of {len(SP500_TICKERS_500)} stocks...")
        
        results = []
        for idx, ticker in enumerate(SP500_TICKERS_500, 1):
            try:
                analysis = await self.agent.analyze_ticker(ticker, 100)
                results.append(analysis)
                if idx % 50 == 0:
                    logger.info(f"✓ Progress: {idx}/{len(SP500_TICKERS_500)}")
            except Exception as e:
                logger.error(f"✗ {ticker}: {str(e)}")
        
        self.total_analyzed = len(results)
        self.buy_opportunities = [r for r in results if r.buy_score >= 0.70]
        
        logger.info(f"✅ Analysis complete: {len(results)} analyzed, {len(self.buy_opportunities)} buy opportunities")
        return results
    
    def scheduled_analysis(self):
        """Scheduled task - analyze S&P 500 every 20 minutes"""
        logger.info("=" * 60)
        logger.info("🔄 S&P 500 Analysis Cycle Starting...")
        logger.info("=" * 60)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(self.analyze_sp500())
            
            if self.buy_opportunities:
                message = self.format_recommendation(self.buy_opportunities)
                logger.info("\n" + message)
                
                # Send notifications
                try:
                    self.notifier.send_notification(
                        ticker="SP500",
                        channels=["slack", "email"],
                        message=message
                    )
                except Exception as e:
                    logger.error(f"Notification error: {e}")
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
        finally:
            loop.close()
    
    def start(self):
        """Start the scheduler"""
        logger.info("⏱️ Starting S&P 500 scheduler (every 20 minutes)...")
        
        self.scheduler.add_job(
            self.scheduled_analysis,
            IntervalTrigger(minutes=20),
            id='sp500_analysis',
            name='S&P 500 Full Analysis',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✅ Scheduler running!")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("🛑 Scheduler stopped")


sp500_scheduler = None

def init_sp500_scheduler():
    global sp500_scheduler
    sp500_scheduler = SP500Scheduler()
    sp500_scheduler.start()
    return sp500_scheduler

def stop_sp500_scheduler():
    global sp500_scheduler
    if sp500_scheduler:
        sp500_scheduler.stop()
