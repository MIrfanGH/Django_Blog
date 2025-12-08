
# Send Welcome Email Asynchronously

from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.conf import settings
import logging


logger = logging.getLogger(__name__)

User = get_user_model()



# ==================== EMAIL NOTIFICATION TASKS ====================

@shared_task(bind=True, max_retries=3)
def post_notifying_email(self, username, user_email):
    
    """ Send email notification when user creates a new blog post. """

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
        logger.info(f"Post creation email sent successfully to {user_email}")

    except Exception as exc:
        logger.error(f"Failed to send post creation email to {user_email}. Error: {exc}")

        # Retry after 5 minutes
        raise self.retry(exc=exc, countdown=300)
    

 
@shared_task(bind=True, max_retries=3)
def post_update_notifying_email(self, username, user_email):
    
    """ Send email notification when user updates a blog post. """

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
        logger.info(f"Post update email sent successfully to {user_email}")

    except Exception as exc:
        logger.error(f"Failed to send post update email to {user_email}: {exc}")
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



# ========== CELERY BEAT SCHEDULE [Schedule taks to inform a non active user] ==========

 
from django.utils import timezone
from datetime import timedelta

@shared_task
def send_blog_reminder():

    """
    Celery Beat periodic task to re-engage inactive users.   
    Identifies users who haven't posted in the last 10 days and sends
    them a friendly reminder email to encourage continued engagement.
    
    Monitoring:
        > Returns count for Celery monitoring tools
    """

    ten_days_ago = timezone.now() - timedelta(days=10)
    
    try: 
        # Query optimization: Get inactive users in a single database hit
        # distinct() ensures each user appears only once even with multiple old posts
        inactive_users = User.objects.filter(
            is_active=True,
            # Assuming you have a related_name='posts' on your Blog model
        ).exclude(
            post__date_posted__gte=ten_days_ago  # # Exclude users with recent posts,  __gte means "greater than or equal to"
        ).distinct()
        
         
        if inactive_users.count() == 0:
            logger.info("No inactive users found for reminder emails")
            return "No inactive users to remind"

        for user in inactive_users:
            try:
                send_mail(
                    subject='We miss your posts!',
                    message=f'Hi {user.username}, you haven\'t posted in a while...write your thoughts whenever its heavy',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception as email_exc:
                # Log individual email failures but continue processing others
                logger.warning(f"Failed to send reminder to {user.email}, Error: {email_exc}")
                continue

        logger.info(f"Reminder email send to {inactive_users.count()} users.")
        return f"Sent reminders to {inactive_users.count()} inactive users"

    except Exception as exc:
        logger.error(f"Blog reminder task failed :  {exc}")
        return f"Email could not be sent"