from django.contrib import admin

from . models import Donation


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):

    # Shows donation status right in the table view (
    list_display = ('id', 'donor_name', 'donor_email', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at') # Adds sidebar filters for quick filtering (e.g., pending/succeeded)
    search_fields = ('donor_name', 'donor_email')     # Helps search donations by name or email.
    readonly_fields = ('created_at',)#,'id', 'donor_name', 'donor_email', 'amount', 'status', )

    # Prevent status change manually (only webhook should update it)
    # def has_change_permission(self, request, obj=None):
    #     return False