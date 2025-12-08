import logging

from django.core.mail import send_mail
from celery import shared_task

# Configure logger
logger = logging.getLogger(__name__)


@shared_task
def send_donation_appreciation_email(donor_name, donor_email):
    """
    Sends a thank you email to donors after successful donation.
    
    Celery task that runs asynchronously to avoid blocking the webhook response. 
    If email sending fails, it's logged but doesn't
    affect the donation processing.

    """
    try:
        send_mail(
            subject="Thank You for Your Donation ❤️",
            message=f"Dear {donor_name},\n\nThank you for your generous donation! Your support means a lot to us.\n\nWarm regards,\nThe Blog Team",
            from_email="irfan55iimtgn@gmail.com",
            recipient_list=[donor_email],
            fail_silently=False  # Changed to False so we can catch and log exceptions
        )
        logger.info(f"Successfully sent appreciation email to {donor_email} ({donor_name})")
        
    except Exception as e:
        # Log the error but don't raise - we don't want email failures to affect donation processing
        logger.error(f"Failed to send appreciation email to {donor_email} ({donor_name}): {str(e)}")