# Import essential shortcuts and utilities
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required # Ensures only logged-in users access certain views

# Import custom forms for registration and profile management
from .forms import UserRegistrationForm, UserUpdateForm, ProfileUpdateForm


""" 
View to handle user account registration 
-On POST: validates and save the form, show success message, and redirect to login.
-On GET, renders an empty registration form.
"""
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)

        # Validate form inputs
        if form.is_valid():
            form.save() # Create new user
            username = form.cleaned_data.get('username')
            messages.success(request, f'Welcome!  Account created for user: {username}. Please Login To Proceed.')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    # Render the registration page with the form
    return render(request, 'users/register.html', {'form':form})



""" 
View to allow logged-in users to update their profile.
- Handles both forms user model and profile (including image uploads)
- Redirects after POST to prevent duplicate submissions
"""
@login_required 
def profile(request):
    if request.method == 'POST':

        # Populate forms with POST data and current user instance
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST,
                                        request.FILES,  # Handles uploaded files (profile images)
                                        instance=request.user.profile, 
                                        )   
             
        # Validate both forms before saving
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, f'Account updated successfully !')
            return redirect('profile') # Redirect to same-page (profile) to prevent resubmission on refresh
    else:
        # On GET request, pre-fill forms with current-user-data
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.profile)

    # Context dictionary(forms) passed to template for rendering
    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }

    return render(request, 'users/profile.html', context) 