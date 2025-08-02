from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile



""" Signal to automatically create a Profile instance whenever a new User is created """
@receiver(post_save, sender=User)  
def create_profile(sender, instance, created, **kwargs):
    if created: # Created is True only If it's the first time
        Profile.objects.create(user=instance) 


""" Signal to automatically save the related Profile whenever the User is saved """ 
@receiver(post_save, sender=User) # Triggered after a User instance is saved
def save_profile(sender, instance, **kwargs):
    instance.profile.save()