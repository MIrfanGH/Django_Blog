from django.conf import settings
import logging
from typing import Optional

from groq import Groq




logger = logging.getLogger(__name__)

GROK_SUMMARIZATION_KEY = settings.GROK_SUMMARIZATION_KEY


def generate_blog_summary(text: str) -> Optional[str]:
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

        if not GROK_SUMMARIZATION_KEY:
            logger.error("Summarization API key not set. Please configure GROK_SUMMARIZATION_KEY")
            return None
        # Set up the Groq client to access their LLM API
        client = Groq(api_key=GROK_SUMMARIZATION_KEY)

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
            temperature=0.3 # Temperature controls randomness; 0.3 keeps responses stable and factual (no creativity randomness)
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.exception("Groq summarization failed")
        return None


