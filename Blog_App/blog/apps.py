from django.apps import AppConfig


class BlogConfig(AppConfig):
    """ App configuration for the Blog application.
        Handles app-specific settings and initialization """
    
    # Sets the default type(to BigAutoField) for auto-incrementing primary keys in models
    default_auto_field = 'django.db.models.BigAutoField'

    # Defines the name of the app (should match the app directory)
    name = 'blog'
