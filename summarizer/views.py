import logging
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from blog.models import Post
from .services import generate_blog_summary
from django.core.cache import cache

from django.contrib import messages
logger = logging.getLogger(__name__)


import logging
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.cache import cache
from blog.models import Post
from .services import generate_blog_summary

logger = logging.getLogger(__name__)


@require_POST
def summarize_post(request, post_id):
    """
    Generate or retrieve cached AI summary for a blog post.
    Redirects back to referrer with summary parameter on success.
    """
    post = get_object_or_404(Post, id=post_id)
    cache_key = f"post_summary_{post.id}"
    summary = cache.get(cache_key)

    if not summary:
        summary = generate_blog_summary(post.content)
        
        if not summary:
            messages.error(request, "Failed to generate summary. Please try again.")
            logger.error(f"Failed to generate summary for post: {post.title}")
            return redirect(request.META.get('HTTP_REFERER', 'blog_home'))
        
        cache.set(cache_key, summary, 60 * 60)  # Cache for 1 hour

    # Redirect back with summary parameter
    referer = request.META.get('HTTP_REFERER', 'blog_home')
    separator = '&' if '?' in referer else '?'
    return redirect(f"{referer}{separator}show_summary={post.id}#post-{post.id}")

