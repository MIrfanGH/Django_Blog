from django.db import models

class Donation(models.Model):

    """
    Represents a donation made by a user.

    The record is first created with 'pending' status before payment,
    and updated to 'succeeded' or 'failed' based on Stripe webhook events.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ]

    donor_name = models.CharField(max_length=100, blank=True, null=True)
    donor_email = models.EmailField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        # Readable representation for admin panel and debugging.
        return f"{self.donor_name or 'Anonymous'} - ${self.amount} ({self.status})"



class ProcessedEvent(models.Model):
    """
    Stores Stripe webhook event IDs to ensure idempotency.

    Why separate model?
    - One Stripe event ≠ one Donation (future-proof: refunds, disputes, etc.)
    - Prevents duplicate processing across ALL webhook types
    - Keeps idempotency logic independent from business data
    - Enables global deduplication (not tied to a single table)
    """
    event_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_id