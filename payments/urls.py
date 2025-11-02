from django.urls import path
from payments.views import (
            Donation_landing_page,
            CreateDonationCheckoutSession,
            Success,
            Cancel,
            my_webhooks_view,

            
)


urlpatterns = [
    path("", Donation_landing_page.as_view(), name="donation_landing_page"),
    path("create-donation-session/", CreateDonationCheckoutSession.as_view(), name="create-donation-session"),
    path("webhooks/stripe/", my_webhooks_view, name="stripe-webhooks"),
    path("success/", Success.as_view(), name="success"),
    path("cancel/", Cancel.as_view(), name="cancel"),

]

