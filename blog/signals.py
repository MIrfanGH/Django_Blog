from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from .models import Post

# Logger for recording cache invalidation events (useful in production debugging)
logger = logging.getLogger(__name__)


def invalidate_post_cache(post):
    """
    Clears all cached data for a post on create, update, or delete.

    Clears:
    - Homepage post list
    - Author's personal post list
    - Post detail page — cache_page generates internal hashed keys that
        can't be reconstructed manually, so we use delete_pattern()
        (available because we're using django-redis as our cache backend)
    """
    username = post.author.username
    pk = post.pk

    cache.delete("post_list_view")
    cache.delete(f"user_posts_{username}")
    cache.delete_pattern(f"*post_detail*{pk}*")

    logger.info("Cache invalidated for Post(id=%s, author=%s)", pk, username)
    
 

@receiver(post_save, sender=Post)
def post_saved(sender, instance, created, **kwargs):
    """
    Triggered automatically after a Post is created or updated.

    Why needed:
    ----------
    - Saving a post means the cached version is no longer accurate.
    - We call the invalidation function to clear stale caches.
    """
    try:
        invalidate_post_cache(instance)
    except Exception:
        # Logs full traceback if anything goes wrong
        logger.exception(
            "Error invalidating cache for saved post %s",
            instance.pk
        )


@receiver(post_delete, sender=Post)
def post_deleted(sender, instance, **kwargs):
    """
    Triggered automatically after a Post is deleted.

    Why needed:
    ----------
    - A deleted post should no longer appear in any cached lists.
    - So we clear all caches related to it.
    """
    try:
        invalidate_post_cache(instance)
    except Exception:
        # Logs full traceback for debugging issues during deletion
        logger.exception(
            "Error invalidating cache for deleted post %s",
            instance.pk
        )
