from django.db import models
from django.contrib.auth.models import User
from PIL import Image




class Profile(models.Model):
    """ Extends the built-in User model to include profile image support.
        Automatically resizes uploaded images larger than 300x300 pixels. """
    user = models.OneToOneField(User, on_delete=models.CASCADE) # Links one User to one Profile
    image = models.ImageField(default='default.jpg', upload_to='profile_pics/')


    # First save the instance to ensure self.image.path is available.
    def __str__(self):
        return f"{self.user.username} Profile"
    
""" Commented these as we are using S3 for file usage and pillo will cause eror for resizing (AWS lambda instead) """
    # def save(self,*args, **kwargs):      
    #     """ Overrides the save method to resize the profile image if its dimensions exceed 300x300 pixels. 
    #         This helps optimize storage and improve page load times also ensures consistent image size for better UI"""  
             
    #     super().save(*args, **kwargs) # Save instance to generate image path

    #     image = Image.open(self.image.path)  # Open the uploaded image file (after it's saved to disk)  
    #     if image.height > 300 or image.width > 300:
    #         final_size = (300, 300)
    #         image.thumbnail(final_size)  # Maintains aspect ratio
    #         image.save(self.image.path)  # Overwrites original image with resized version
