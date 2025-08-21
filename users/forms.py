from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import Profile


"""
A custom user registration form extending Django's built-in UserCreationForm
Adds an email field to the default fields
"""
class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField()  

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


"""
UserUpdateForm: Allows logged-in users to update their basic account info
Reuses the built-in User model and focuses on editable fields
"""
class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()  

    class Meta:
        model = User
        fields = ['username', 'email']


"""
ProfileUpdateForm: Enables users to update their profile picture
Separate form for modularity (as it uses custom model 'Profile') and better UX in frontend integration
"""
class ProfileUpdateForm(forms.ModelForm):
 
    class Meta:
        model = Profile
        fields = ['image']