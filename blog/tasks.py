
# Send Welcome Email Asynchronously

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def post_notifying_email(self, username, user_email):
    
    subject = 'Posted created successfully'

    message = (
        f"Hi {username}, \n\n"
        "You successfully created a post on MyDailyBlog, I hope it was a good experience for you.\n"
        
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False
        )

        logger.info(f"Blog posting email sent to {user_email}")
    except Exception as exc:
        logger.error(f"Failed to send email to {user_email}: {exc}")
        # Retry after 5 minutes
        raise self.retry(exc=exc, countdown=300)
    


@shared_task(bind=True, max_retries=3)
def post_update_notifying_email(self, username, user_email):
    
    subject = 'Updated post successfully'

    message = (
        f"Hi {username}, \n\n"
        "You successfully updated a blog on MyDailyBlog\n"
        
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False
        )

        logger.info(f"Blog update email sent to {user_email}")
    except Exception as exc:
        logger.error(f"Failed to send email to {user_email}: {exc}")
        # Retry after 5 minutes
        raise self.retry(exc=exc, countdown=300)
    


# Notify user when they delete a post
@shared_task(bind=True, max_retries=3)
def notify_post_deletion(self, username, user_email, post_title):

    subject = 'Post Deleted Successfully'
    message = (
        f"Hi {username},\n\n"
        f'Your post "{post_title}" has been successfully deleted from MyDailyBlog.\n\n'
        f"You can always create new posts anytime!\n"
    )
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False
        )
        logger.info(f"Post deletion email sent to {user_email}")
    except Exception as exc:
        logger.error(f"Failed to send deletion email: {exc}")
        raise self.retry(exc=exc, countdown=300)
