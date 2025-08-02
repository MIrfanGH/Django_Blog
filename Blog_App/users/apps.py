from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'


    def ready(self):
        """ This method is called when the app is fully loaded.
            Used here to import and register signal handlers defined in users/signals.py
            so that they are active when the app starts """
        
        # Importing thses here ensures signals are connected only after 
        # everything(models, apps, and settings) is properly loaded
        import users.signals