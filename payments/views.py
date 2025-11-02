import stripe
from stripe import SignatureVerificationError 

import json
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.conf import settings
from . models import Donation
from django.http import  JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView



stripe.api_key = settings.STRIPE_SECRET_KEY  # This key authenticates all API requests/calls to Stripe



# ========================== FRONTEND: DONATION LANDING PAGE ==========================
class Donation_landing_page(View):
    def get(self, request):
      context = {
          'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY 
      }
      # The Stripe public key is passed to the template to initialize Stripe.js on the client side
      return render(request, 'payments/checkout.html', context) 




# ========================== BACKEND: CREATE CHECKOUT SESSION ==========================

"""
Creates a Stripe Checkout Session for donation payment.

Flow:
1. Receive donation amount from frontend
2. Create a pending donation record in database
3. Create Stripe checkout session with donation metadata
4. Return session ID to frontend for redirect

The donation is created with 'pending' status and will be updated
to 'succeeded' via webhook after successful payment.
"""

class CreateDonationCheckoutSession(View):
    def post(self, request, *args, **kwargs):
        
        # Base URL for redirect after payment
        YOUR_DOMAIN = "http://127.0.0.1:8000"

        # Parse JSON body from frontend (contains donation amount)
        data = json.loads(request.body)  
        amount = int(float(data.get("amount")) * 100)  # Stripe uses cents
        if amount <= 0:
            return JsonResponse({"error": "Invalid amount"}, status=400)
        

         # Create donation record with pending status (no name/email yet), create BEFORE payment to track the attempt
        donation = Donation.objects.create(
            amount=float(amount) / 100,  # Convert back to dollars for database
            status='pending',
            donor_name = '',
            donor_email = '',
        )

        # Create stripe  checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{    # Define what the customer is paying for
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': amount,
                    'product_data': {
                        'name': 'Donation to keep alive this Blog ❤️',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',  # One-time payment (not subscription)
            metadata={

                "donation_id":donation.id,
            },

            # Redirect URLs after payment
            success_url=YOUR_DOMAIN + '/payments/success/',
            cancel_url=YOUR_DOMAIN + '/payments/cancel/',
        )


        return JsonResponse(
            {
                'id': session.id
            })         

# ========================== SUCCESS & CANCEL PAGES ==========================

class Success(TemplateView):
    template_name = 'payments/success.html'

class Cancel(TemplateView):
    template_name = 'payments/cancel.html'



# ========================== STRIPE WEBHOOK ENDPOINT ==========================


@csrf_exempt   # Disable CSRF for webhooks as it's not a browser form submission(but sent from Stripe’s servers directly to Django backend), a server-to-server call 
def my_webhooks_view(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    # Verify the webhook signature to ensure request is from Stripe
    # prevents malicious actors from sending fake payment confirmations
    try:  
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET_KEY 
        )
    except ValueError:
        return HttpResponse(status=400) 
    except SignatureVerificationError :
        return HttpResponse(status=400)

    # Handle the checkout.session.completed event triggered when a customer successfully completes payment
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # Retrieve the donation ID (to update the record) 
        donation_id = session['metadata'].get('donation_id')

        # Extract customer details from Stripe's checkout session (collected by Stripe during checkout)
        customer_name = session['customer_details']['name']
        customer_email = session['customer_details']['email']


        # Update the pending donation record with payment confirmation
        try:
            donation = Donation.objects.get(id=donation_id)
            donation.donor_name = customer_name  
            donation.donor_email = customer_email
            donation.status = 'succeeded'
            donation.save()
            

            # Send appreciation email
            send_mail(
                subject="Thank You for Your Donation ❤️",
                message=f"Dear {donation.donor_name},\n\nThank you for your generous donation! Your support means a lot to us.\n\nWarm regards,\nThe Blog Team",
                from_email="support@yourblog.com",
                recipient_list=[donation.donor_email],
                fail_silently=True  # Prevents webhook failure if email sending fails
            )
        except Donation.DoesNotExist:
            # In case donation record was deleted or not found
            pass  

    # Always return 200 to acknowledge receipt (prevents repeated Stripe retries)
    return HttpResponse(status=200)



# ========================== OPTIONAL: MANUAL FULFILLMENT HANDLER ==========================
# def my_fullfilment_view(session_id):
#     """
#     Example placeholder for advanced logic like:
#     - Generating invoices
#     - Assigning user credits
#     - Sending Slack notifications
#     """
#     pass