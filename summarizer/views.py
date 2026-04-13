from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from blog.models import Post
from .services import get_post_summary

import time
from django.contrib import messages
import logging
from django.shortcuts import get_object_or_404, redirect 
from django.core.cache import cache
from django.contrib import messages
from blog.models import Post


logger = logging.getLogger(__name__)

# Number of requests allowed per user within the time window, preventing abuse of LLM calls.
RATE_LIMIT_REQUESTS = 5  
RATE_LIMIT_WINDOW  = 60 



def is_rate_limited(request) -> bool:
    """
    - Simple rate limiting function using cache
    - It tracks the number of summarization requests per user (or IP for anonymous users) within a defined time window.
    - Thus helps to prevent abuse of the summarization feature and excessive calls to the LLM API, 
        which could lead to performance issues or increased costs.
    """

    if request.user.is_authenticated:
        key = f"Summarize-RL:user:{request.user.id}"
    else:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "unknown"))
        key = f"Summarize:IP:{ip}"

    # key = user_key if request.user.is_authenticated else ip_key 

    count = cache.get(key, 0) 
    if count >= RATE_LIMIT_REQUESTS:
        return True # Rate limit exceeded
    
    # Increment the count and set expiration only if it's the first request in the window
    cache.set(key, count + 1, timeout=RATE_LIMIT_WINDOW)
    return False # Not rate limited



@require_POST
def summarize_post(request, post_id):
    """
    View to handle the request response cycle for the AI summarization of a blog post.
    """

    if is_rate_limited(request):
        logger.warning(f"Too many requests. Please wait before summaizing again.")
        messages.info(request, "Too many requests. Please wait before summarizing again.")
        return redirect(request.META.get('HTTP_REFERER', 'blog_home'))

    post = get_object_or_404(Post, id=post_id)
    summary = get_post_summary(post)

    # If summary is not immediately available, we wait briefly and check again before redirecting.
    # To avaoid the manual refresh, we can implement a simple polling mechanism later to delever summary asynchronously without delaying the UX.
    if not summary:     
        time.sleep(3)
        summary = get_post_summary(post)  # check once more after waiting

    referer = request.META.get('HTTP_REFERER', 'blog_home')

    if not summary:
        messages.info(request, "Summary is being generated...Please refresh!")
        return redirect(request.META.get('HTTP_REFERER', 'blog_home'))
    
    # Redirect back with summary parameter
    referer = request.META.get('HTTP_REFERER', 'blog_home')
    separator = '&' if '?' in referer else '?'
    return redirect(f"{referer}{separator}show_summary={post.id}#post-{post.id}")
