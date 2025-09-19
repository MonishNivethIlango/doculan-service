# from celery import Celery
#
# celery_app = Celery("doc_scheduler", broker="redis://localhost:6379/0")
# celery_app.conf.task_routes = {
#     "app.tasks.email_tasks.send_reminder_email": {"queue": "email_queue"},
# }
# send_reminder_email = celery_app.task(name="app.tasks.email_tasks.send_reminder_email")
