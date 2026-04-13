from django.db import models

class PostSummary(models.Model):
    post = models.OneToOneField(
        'blog.Post',
        on_delete=models.CASCADE,
        related_name='summary'
    )
    summary = models.TextField()

    # decide whether to reuse or regenerate summary based on content changes
    content_hash = models.CharField( 
        max_length=64,
        db_index=True # Indexing this field allows for faster lookups
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    generation_time_ms = models.IntegerField(null=True, blank=True)
    generation_model = models.CharField(max_length=50, null=True, blank=True)


    def __str__(self):
        return f"Summary for: {self.post.title} | {self.summary[:50]}" 