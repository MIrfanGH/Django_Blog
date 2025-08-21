"""
Main URL configuration for users app.
Defines routes for registration, authentication, and user profile management
"""

from django.urls import path
from users import views as users_views
from django.contrib.auth import views as auth_views


urlpatterns = [

    # User registration and profile routes
    path('register/', users_views.register, name='register'),
    path('profile/', users_views.profile, name='profile'),

    # Authentication views using Django's built-in auth system
    path('login/', auth_views.LoginView.as_view(template_name="users/login.html"), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name="users/logout.html"), name='logout'),

]

 
