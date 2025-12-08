# Import essential shortcuts and utilities
from django.forms import ValidationError
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required # Ensures only authenticated users access restricted views
from django.db import DatabaseError, transaction  # Django's transaction management API — used to wrap DB operations in atomic blocks (all‑or‑nothing consistency)

from .forms import UserRegistrationForm, UserUpdateForm, ProfileUpdateForm
from .tasks import profile_update_email, process_profile_image
import logging



logger = logging.getLogger(__name__)



def register(request):
    """
    Handle new user account registration.
    
    GET Request:
        - Displays empty registration form
    
    POST Request:
        - Validates form data (username, email, password)
        - Creates new User account
        - Shows success message
        - Redirects to login page

    Production Notes:
        - Password automatically hashed by UserCreationForm
        - Username uniqueness enforced at database level
        - Email validation handled by form clean methods

    """
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)

        try:

            # Validate form inputs (username, email, passwords match, etc.)
            if form.is_valid():
                # Save user to database (password is automatically hashed)
                form.save()
                username = form.cleaned_data.get('username') 

                logger.info(f"New user registered: {username}")               
                messages.success(request, f'Welcome!  Account created for user: {username}. Please Login To Proceed.')
                return redirect('login')
            else:
                # Form validation failed - errors will be displayed in template
                # as when render() is called, the form (with its errors) is passed back to the template, and Django will display the error messages.

                logger.warning(f"Registration form validation failed: {form.errors}")

        except Exception as e:
            # Catch all unexpected errors
            logger.error(f"Unexpected error during registration: {e}", exc_info=True)
            messages.error(
                request,
                'An unexpected error occurred. Please try again.'
            )
    else: 
        # GET request - display empty form
        form = UserRegistrationForm()
        
    return render(request, 'users/register.html', {'form':form})




@login_required 
def profile(request):

    """
    Allow authenticated users to view and update their profile.
    
    Features:
        - Update username and email (User model)
        - Update bio and profile image (Profile model)
        - Async image processing via Celery
        - Async email notification
        - Transaction safety for data consistency
    
    GET Request:
        - Displays forms pre-filled with current user data
    
    POST Request:
        - Validates both forms
        - Saves changes atomically (both or neither)
        - Triggers async image resize if new image uploaded
        - Sends confirmation email
        - Redirects to prevent duplicate submissions
    
    Production Notes:
        - Uses database transactions for atomicity
        - transaction.on_commit() ensures Celery tasks only fire after DB commit
        - Image processing happens asynchronously (non-blocking)
        - Old images cleaned up by Celery task
    
    Performance:
        - Image upload ~50-200ms (depends on file size)
        - Celery task queued immediately, processed in background
        - User sees success message instantly, image optimized within seconds
    
    Error Handling:
        - Database errors rolled back automatically
        - Image processing errors don't break profile update
        - Email failures handled by Celery retry mechanism
    """
    if request.method == 'POST':

        # Populate forms with POST data and current user/profile instances
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST,
                                        request.FILES,  # Handles uploaded files (profile images)
                                        instance=request.user.profile, 
                                        )   
        try:  
            # Validate both forms before saving
            if user_form.is_valid() and profile_form.is_valid():
                image_changed = 'image' in request.FILES
                old_image_path = request.user.profile.image.name if image_changed else None

                # Save both forms in a transaction to ensure data integrity and atomicity
                # If either save fails, both are rolled back
                with transaction.atomic():
                    user_form.save()
                    profile_instance = profile_form.save()
                    logger.info(
                        f"Profile updated for user {request.user.username}. "
                        f"Image changed: {image_changed}"
                    )
                
                if image_changed:

                    new_image_path = profile_instance .image.name

                    # Queue async tasks AFTER successful DB commit
                    # transaction.on_commit ensures tasks only run if DB save succeeds
                    transaction.on_commit(
                        lambda: process_profile_image.delay(user_id=request.user.id, image_path=new_image_path)  # inline function since on_commit takse a funtion
                    )
                    messages.success(request, 'Profile updated! Your image is being optimized.')
                else:
                    messages.success(request, f'Account updated successfully !')        
                        
                # Send confirmation email if profile updated ( regardless of image change)
                transaction.on_commit(
                    lambda: profile_update_email.delay(request.user.email, request.user.username)
                )           
                return redirect('profile') # Redirect to same-page (profile) to prevent duplicate form submission on browser refresh
            else:
                 # Form validation failed - display errors to user
                logger.warning(
                    f"Profile update validation failed for {request.user.username}. "
                    f"User form errors: {user_form.errors}, "
                    f"Profile form errors: {profile_form.errors}"
                )
                messages.error(
                    request,
                    'There seems to be some error in your form,  Please make corrections .'
                )

        # ==================== Handling Possible Exceptions ====================
        except DatabaseError as e:
            # Database errors (connection issues etc.)
            # Transaction automatically rolled back
            logger.error(
                f"Database error during profile update for {request.user.username}: {e}",
                exc_info=True
            )
            messages.error(
                request,
                'A database error occurred. Your changes were not saved. Please try again.'
            )

        except ValidationError as e:
            # Model-level validation failed (can occur even if forms pass validation,
            # e.g. DB-level issues, or corrupted file uploads)
            logger.error(
                f"Validation error during profile update for {request.user.username}: {e}",
                exc_info=True
            )
            messages.error(
                request,
                'Invalid data provided. Please check your inputs and try again.'
            )


        except Exception as e:
            # Catch-all for unexpected errors (file system, memory, etc.)
            logger.error(
                f"Unexpected error during profile update for {request.user.username}: {e}",
                exc_info=True
            )
            messages.error(
                request,
                'An unexpected error occurred. Please try again later.'
            )

    else:
         # GET request - pre-fill forms with current user data
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)

    # Context passed to template
    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }

    return render(request, 'users/profile.html', context) 