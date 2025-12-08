from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from .models import Post

# Logger for recording cache invalidation events (useful in production debugging)
logger = logging.getLogger(__name__)


def invalidate_post_cache(post):
    """
    Remove all cached data related to a Post object.

    Why this function exists:
    --------------------------
    - Whenever a post is created, updated, or deleted,
      the cached copies become outdated (stale).
    - We clear all cache entries where this post is shown.

    What gets cleared:
    ------------------
    1. Global post list (homepage)
    2. Author's personal post list
    3. Post detail page 
    4. Django cache_page() generated key for detail view
       (Django uses its own key format internally)
    """

    # Extract reusable info
    username = post.author.username
    pk = post.pk

    # List of cache keys we want to delete
    keys = [
        "post_list_view",                         # Cached homepage list
        f"user_posts_{username}",                 # Cached posts by that specific user
        f"post_detail_{pk}",                      # Cached detail page
        f"post_detail.views.decorators.cache.cache_page..{pk}.",  
        # ^ Django's internal cache_page key format
    ]

    # Delete keys that exist → cache.delete returns True/False
    removed = [key for key in keys if cache.delete(key)]

    # Log which keys were actually deleted (useful in debugging)
    logger.info(
        "Cache invalidated for Post(id=%s, author=%s): %s",
        pk,
        username,
        removed or "none",   # Shows "none" if no keys existed
    )
 

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
