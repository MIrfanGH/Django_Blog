import logging
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from blog.models import Post
from .services import generate_blog_summary
from django.core.cache import cache

logger = logging.getLogger(__name__)


@require_POST   # restricts access to the view so that only HTTP POST requests are allowed.
def summarize_post(request, post_id):
    """
    Synchronous summarization using AI.
    """
    post = get_object_or_404(Post, id=post_id)

    cache_key = f"post_summary_{post.id}"
    summary = cache.get(cache_key)
    
    if summary:  # To prevents the case where :  AI fails then summary = None, none cached for 1 hour
        summary = cache.get(cache_key)

    if not summary:
        summary = generate_blog_summary(post.content)
        cache.set(cache_key, summary, 60 * 60)

    # store post-specific summary in session
    request.session["ai_summary"] = {
        "post_id": post.id,
        "summary": summary,
    }
     # Get the referrer URL to redirect back to the same page
    referer = request.META.get('HTTP_REFERER')
    if referer:
        # Add anchor to scroll to the specific post
        return redirect(f"{referer}#post-{post.id}")
    
    return redirect("blog_home")
  
