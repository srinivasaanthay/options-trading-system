"""
Integration code to add to app.py lifespan
"""

from sp500_scheduler import init_sp500_scheduler, stop_sp500_scheduler

# Add this to the app lifespan:

async def lifespan(app):
    # Startup
    print("🚀 Starting S&P 500 Scheduler...")
    init_sp500_scheduler()
    yield
    # Shutdown
    print("🛑 Stopping S&P 500 Scheduler...")
    stop_sp500_scheduler()

# Then update FastAPI initialization:
# app = FastAPI(title="Trading System", lifespan=lifespan)
