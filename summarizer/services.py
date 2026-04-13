from django.conf import settings
import logging
from typing import Optional
from celery import shared_task
from groq import Groq

from blog.models import Post
from .utils import generate_content_hash
from django.core.cache import cache
from .models import PostSummary
import time

logger = logging.getLogger(__name__)

GROQ_SUMMARIZATION_KEY = settings.GROQ_SUMMARIZATION_KEY
SUMMARY_TIMEOUT_SEC = 10 # # Max time to wait for Groq API response — prevents celery worker hanging indefinitely 


def generate_post_summary(text: str) -> Optional[str]:
    """
    Generates a concise AI-powered summary for a blog post.

    This function makes a synchronous request to Groq's LLM inference API,
    utilizing Meta's LLaMA 3.3 (70B) large language model to summarize
    long-form blog content into 3–4 clear, factual lines.

    Design goals:
        - Preserve the original meaning of the content
        - Avoid hallucinations or introduction of new facts
        - Keep the summary short, neutral, and readable
    Args:
        text (str): Full blog content to be summarized.
    Returns:
        Optional[str]: Generated summary text if successful,
                       otherwise None in case of failure.
    """
    try:

        if not GROQ_SUMMARIZATION_KEY:
            logger.error("Summarization API key not set. Please configure GROK_SUMMARIZATION_KEY")
            return None
        # Set up the Groq client to access their LLM API
        client = Groq(api_key=GROQ_SUMMARIZATION_KEY)

        # Prompt explicitly instructs the LLM to summarize without altering facts
        prompt = f"Summarize the following blog post in 3-4 concise lines.\
                Preserve meaning and do not add new facts.\n\n{text}"
        
        # Make the API call  
        response = client.chat.completions.create(

            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert blog summarizer."},
                {"role": "user", "content": prompt}
            ],

            # Low temperature ensures deterministic, factual summaries,   no creativity randomness
            temperature=0.3, # Temperature controls randomness; 0.3 keeps responses stable and factual (no creativity randomness)
            timeout= SUMMARY_TIMEOUT_SEC # Groq client(as client natively supports a timeout parameter) timeout — kills hanging requests after 10
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.exception("Groq summarization failed")
        return None



@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def generate_post_summary_task(self, post_id, content, content_hash): # creating separate functin cause celery task cannot return value and we need to update the summary in DB after generation.

    lock_key = f"summary_lock:{post_id}:{content_hash}" # Lock key defined out of try block to ensure it's available in the finally block even if an exception occurs before its definition.
    cache_key = f"summary:{post_id}:{content_hash}"

    try:
        start = time.time()
        summary = generate_post_summary(content)
        generation_time = int((time.time() - start) * 1000)

        if not summary:
            return

        PostSummary.objects.update_or_create(
            post_id=post_id,
            defaults={
                "summary": summary,
                "content_hash": content_hash,
                "generation_time_ms": generation_time,
                "generation_model": "llama-3.3-70b-versatile",
            }
        )

        cache.set(cache_key, summary, 3600)

        # Success — release lock immediately to allow any waiting requests to proceed.
        cache.delete(lock_key)
        return summary
    
    except Exception as e:
        logger.exception(
            "Summary generation task failed for post_id=%s", 
            post_id, self.request.retries + 1, self.max_retries + 1) # increment the retires and max_tries by 1 in the log to reflect the current attempt number 

        raise self.retry(exc=e, countdown=2 ** self.request.retries * 5) # Exponential backoff: 10s, 20s, 40s between retries

    finally:
        # Always release the lock — whether we succeeded, failed, or hit an unexpected exception.
        # Without this, a crash leaves the lock alive for 60s and silently blocks all retries.
        if self.request.retries >= self.max_retries: 
            cache.delete(lock_key)
        


def get_post_summary(post: Post) :

    try:
        content = post.content
        current_hash = generate_content_hash(content) # Generate a hash of the current content to check for changes

        cache_key = f"summary:{post.id}:{current_hash}" 
        lock_key = f"summary_lock:{post.id}:{current_hash}" # Lock key to prevent multiple simultaneous summary generations for the same post content

        # CACHE CHECK
        summary = cache.get(cache_key)
        if summary:
            return summary
        
        summary_obj = PostSummary.objects.filter(post=post).first() # DB CHECK for the summary with the same content hash to ensure freshness

        # If summary already exists and valid → return from DB and set cache for future requests. T
        if summary_obj and summary_obj.content_hash == current_hash: 
            cache.set(cache_key, summary_obj.summary, 3600)
            return summary_obj.summary     

        # 3. Only now — trigger async if not already running
        if not cache.get(lock_key):
            cache.set(lock_key, True, timeout=60)
            generate_post_summary_task.delay(post.id, content, current_hash)
        return None
    
    except Exception as e:
        logger.exception("Error retrieving summary for post_id=%s", post.id)
        return None