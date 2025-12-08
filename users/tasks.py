from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

# Import needed to resize task
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile 
from django.core.files.storage import default_storage   # Handles reading/writing files from the configured storage backend (e.g., S3)
from PIL import Image  # Pillow library for image processing (resize, convert, optimize)                                 
import io    # In-memory bytes buffer for temporary file handling                                            
import logging    # Standard Python logging for task/error tracking



logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_email, username):
      
    """
    Celery task: Send welcome email with retry + logging.

    Retries:
        - Up to 3 attempts (bind=True enables self.retry).
        - Waits 5 minutes between retries.
    Args:
        self: Task instance (provided by Celery when bind=True)
        user_email: Recipient email address
        username: User's username for personalization
    """

    subject = 'Welcome to MyDailyBlog'
    message = (
        f"Hi {username},\n\n"
        "Welcome to MyDailyBlog! We're happy to have you on board.\n\n"
        "— The MyDailyBlog Team"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        logger.info(f"Welcome email sent to {user_email}")
    except Exception as exc:
        logger.error(f"Failed to send email to {user_email}: {exc}")
        
        raise self.retry(exc=exc, countdown=300) # Retry after 5 minutes
    


@shared_task(bind=True, max_retries=3)
def profile_update_email(self, user_email, username):

    """ Celery task: Send profile update notification email with retry + logging. """

    subject = "Profile updated"

    message = (
        f"Hi {username}, \n\n"
        "You profile has been updated. \n\n"
         "— The MyDailyBlog Team"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        logger.info(f"Profile update email sent to {user_email}")
    except Exception as exc:
        logger.error(f"Failed to send email to {user_email}: {exc}")

        # bind=True  enables this retry logix  
        raise self.retry(exc=exc, countdown=300)  # Retry after 5 minutes
    



# ================================  Resizing User uploaded images  ================================

User = get_user_model() 

@shared_task(bind=True, max_retries=3)
def process_profile_image(self, user_id, image_path):
    """
    Downloads image from S3 →( Resizes + compress ) → Uploads back to S3 -> Delete old image
    """
    # Get the user and their profile
    try:
        user = User.objects.select_related('profile').get(id=user_id)
        profile = user.profile
        
        # Download image from S3 and open with Pillow
        with default_storage.open(image_path, 'rb') as f:
            img = Image.open(f)
            
            # Convert any image format to RGB (standard format for JPEG)  as PNG can have transparency (RGBA), we need solid RGB for JPEG
            if img.mode != 'RGB':
                img = img.convert('RGB')
        

        # Resize image to max 800x800 (keeps aspect ratio)
        # thumbnail() shrinks but never enlarges
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        
        # Save resized image to memory (not disk)
        buffer = io.BytesIO()  # Creates temporary memory storage
        img.save(buffer, format='JPEG', quality=85)  # Compress to 85% quality
        buffer.seek(0)  # Reset pointer to start of buffer


        # Upload compressed image back to S3 (overwrites original)
        profile.image.save(
            image_path.split('/')[-1],   # Use just filename, not full path
            ContentFile(buffer.read()), 
            save=True
            )
    
        logger.info(f"Profile image optimized for user {user_id}")
        return f"Image optimized successfully for user {user_id}"

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found during image processing")
        raise
    except Exception as exc:
        logger.error(f"Failed to process image for user {user_id}: {exc}")

        # Retry 
        raise self.retry(exc=exc, countdown=300)
             
   

