from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Post   # This signal will work on this model (Post)


@receiver(post_save, sender=Post)
def invalidate_cache_on_post_save(sender, instance, created, **kwargs):
    """Invalidate cache when a post is created or updated"""
    cache_key = f"user_posts_{instance.author.username}"
    cache.delete(cache_key)   
    cache.delete(f"post_detail_{instance.pk}") 
    cache.delete(f"post_list_view")
    if created:
        print(f"Post created by {instance.author.username} - cache cleared")
    else:
        print(f"Post updated by {instance.author.username} - cache cleared")



@receiver(post_delete, sender=Post)
def invalidate_cache_on_post_delete(sender, instance, **kwargs):
    """Invalidate cache when a post is deleted"""
    cache_key = f"user_posts_{instance.author.username}"
    cache.delete(cache_key)
    cache.delete(f"post_detail_{instance.pk}")
    cache.delete(f"post_list_view")
    print(f"Post deleted by {instance.author.username} - cache cleared")
    
