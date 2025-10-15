"""
Main URL configuration for the Blog_App project.

This file maps URL paths to corresponding views or includes app-level URL configurations
"""

from django.contrib import admin
from django.urls import path, include
from users import views as users_views
from django.contrib.auth import views as auth_views

from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [

    # Routes for the blog app (homepage and post-related views)
    path('', include('blog.urls')),

    # Django admin site
    path('admin/', admin.site.urls),

    # Routes for user authentication and profile management
    path('users/', include('users.urls')),


    # Password reset routes 
    path('password-reset/',auth_views.PasswordResetView.as_view(
        template_name='users/password_reset.html'),
        name='password_reset'),
    path('password-reset/done/',auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html'),
        name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>',auth_views.PasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html'),
        name='password_reset_confirm'),
    path('password-reset/complete',auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html'),
        name='password_reset_complete'),

    # Routes for payments management
    path('payments/', include('payments.urls')),


]

# Serve media files (e.g., profile images) during development (when DEBUG = True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
 
