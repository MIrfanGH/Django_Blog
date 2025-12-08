from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile
from .tasks import (
    send_welcome_email,
    profile_update_email,
    )
import logging
from django.db import transaction



logger = logging.getLogger(__name__)



@receiver(post_save, sender=User)  
def create_profile(sender, instance, created, **kwargs):
    """
    Auto-create Profile when new User is registered.
    
    Triggered: After User.save() with created=True
    Actions: Creates linked Profile, queues welcome email
    
    Production Notes:
        - Only runs for NEW users (created=True)
        - Email sent async via Celery (non-blocking)
        - transaction.on_commit ensures email only sent after DB commit
    """
    if created: # Created is True only If it's the first time

        try:
            
            # Create associated Profile instance
            Profile.objects.create(user=instance)
            logger.info(f"Profile created for new user: {instance.username}")
            
            # Queue welcome email after successful DB commit
            # transaction.on_commit() prevents email if transaction rolls back
            transaction.on_commit(
                lambda: send_welcome_email.delay(instance.email, instance.username)
            )
            
        except Exception as e:
            # Don't break user creation if profile fails
            logger.error(
                f"Failed to create profile for {instance.username}: {e}",
                exc_info=True
            )

 


@receiver(post_save, sender=User) # Triggered after a User instance is saved
def save_profile(sender, instance, **kwargs):
    """
    Auto-save Profile when User is updated.
    
    Triggered: After User.save() (updates only, not creation)
    Purpose: Keeps Profile in sync if User model changes
    
    Production Notes:
        - Prevents profiles inconsistencies
        - hasattr check prevents errors if profile doesn't exist
    """
    try:
        # Save profile if it exists
        if hasattr(instance, 'profile'):
            instance.profile.save()
            
    except Exception as e:
        # Log but don't break user save operation
        logger.warning(
            f"Failed to save profile for {instance.username}: {e}",
            exc_info=True
        )

 