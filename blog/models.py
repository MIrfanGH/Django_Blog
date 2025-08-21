from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse # Used to generate URLs by reversing URL patterns by name


class Post(models.Model):
    """ Blog post model linked to a user """

    title = models.CharField(max_length=100)
    content = models.TextField()
    content_nature = models.CharField(max_length=100)
    date_posted = models.DateTimeField(default=timezone.now) # Automatically sets the post's date to current time
    author = models.ForeignKey(User, on_delete=models.CASCADE)  
        # Establishes a one-to-many relationship with the built-in User model
       

    def __str__(self):
        return f"{self.title} - Nature : {self.content_nature}"
    

    def get_absolute_url(self):
        # Returns URL to the post's detail view after creating or updating a post 
        return reverse("post_detail", kwargs={"pk": self.pk})
    

       