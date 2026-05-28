from apscheduler.schedulers.background import BackgroundScheduler

from app.agents import collector, monitor, notifier, optimizer


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Africa/Lagos")
    scheduler.add_job(collector.run, "interval", minutes=15, id="collector", replace_existing=True)
    scheduler.add_job(optimizer.run, "cron", hour=6, minute=0, id="optimizer-daily", replace_existing=True)
    scheduler.add_job(monitor.run, "interval", seconds=30, id="monitor", replace_existing=True)
    scheduler.add_job(notifier.flush, "interval", seconds=10, id="notifier", replace_existing=True)
    scheduler.start()
    return scheduler
