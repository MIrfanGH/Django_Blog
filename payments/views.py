from venv import logger
import stripe
from stripe import SignatureVerificationError 

import json
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.conf import settings

from payments.tasks import send_donation_appreciation_email
from . models import Donation
from django.http import  JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView

# from .tasks import send_donation_appreciation_email



stripe.api_key = settings.STRIPE_SECRET_KEY  # This key authenticates all API requests/calls to Stripe



# ========================== FRONTEND: DONATION LANDING PAGE ==========================

class Donation_landing_page(View):
    """Renders the donation checkout page with Stripe public key."""

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
        
        try: 
            # Parse JSON body from frontend (contains donation amount as well)
            data = json.loads(request.body)  
            amount = int(float(data.get("amount")) * 100)  # Stripe uses cents
            if amount <= 0:
                logger.warning(f"Invalid donation amount attempted: {amount}")
                return JsonResponse({"error": "Invalid amount"}, status=400)
            

            # Create donation record with pending status (no name/email yet), 
            # created BEFORE payment to track the attempt
            donation = Donation.objects.create(
                amount=float(amount) / 100,  # Convert back to dollars for database
                status='pending',
                donor_name = '',
                donor_email = '',
            )
            logger.info(f"Created pending donation record: ID={donation.id}, amount=${donation.amount}")

            # Create stripe  checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{    # Define what the customer is paying for
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': amount,
                        'product_data': {
                            'name': '❤️ Blog Donation (DEMO)',
                            'description': '⚠️ TEST MODE: Use card 4242 4242 4242 4242 | A valid expiration date | Any 3 numbers as CVC |',
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',  # One-time payment (not subscription)

                # ADD THIS: Shows above the Pay button
                custom_text={
                    'submit': {
                        'message': '⚠️ This is a test payment - no real charges will be made'
                    }
                },
                
                metadata={

                    "donation_id":donation.id,
                },

                # Redirect URLs after payment
                success_url = request.build_absolute_uri('/payments/success/'),
                cancel_url = request.build_absolute_uri('/payments/cancel/')
                
            )
            logger.info(f"Created Stripe checkout session: session_id={session.id}, donation_id={donation.id}")

            return JsonResponse(
                {
                    'id': session.id
                })         
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error during checkout session creation: {str(e)}")
            return JsonResponse({"error": "Payment processing error"}, status=500)
        except Exception as e:
            logger.error(f"Unexpected error creating donation checkout session: {str(e)}")
            return JsonResponse({"error": "An error occurred"}, status=500)


# ========================== SUCCESS & CANCEL PAGES ==========================

class Success(TemplateView):
    """Displays success page after completed payment."""
    template_name = 'payments/success.html'


class Cancel(TemplateView):
    """Displays cancel page when user cancels payment."""
    template_name = 'payments/cancel.html'



# ========================== STRIPE WEBHOOK ENDPOINT ==========================


@csrf_exempt   # Disable CSRF for webhooks - this is a server-to-server call from Stripe, not a browser form
def my_webhooks_view(request):

    """
    Handles Stripe webhook events, specifically checkout.session.completed.
    
    This endpoint("webhooks/stripe/") receives notifications from Stripe when payment events occur.
    It verifies the webhook signature to ensure requests are actually from Stripe,
    then updates donation records and triggers thank you emails.
    """

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    # Verify the webhook signature to ensure request is from Stripe
    # prevents malicious actors from sending fake payment confirmations
    try:  
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET_KEY 
        )
        logger.info(f"Webhook event received: type={event['type']}, id={event['id']}")
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {str(e)}")
        return HttpResponse(status=400) 
    except SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {str(e)}")
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

            logger.info(f"Donation {donation_id} marked as succeeded: {customer_name} ({customer_email}) - ${donation.amount}")

            # Send appreciation email 
            if customer_email:
                send_donation_appreciation_email.delay(donation.donor_name, donation.donor_email)
                logger.info(f"Queued appreciation email for donation {donation_id}")
            else:
                logger.warning(f"No email address for donation {donation_id}, skipping appreciation email")
                
        
        except Donation.DoesNotExist:
            logger.error(f"Donation record {donation_id} not found for webhook event")
        except Exception as e:
            logger.error(f"Error processing webhook for donation {donation_id}: {str(e)}")

        # Always return 200 to acknowledge receipt
        # This prevents Stripe from repeatedly retrying the webhook
        return HttpResponse(status=200)
    
    # return 200 to acknowledge receipt for all other events that sripe sends when payment succeeds 
    # Like: payment_intent.created, payment_intent.succeeded, charge.succeeded, charge.updated (we only hndled....checkout.session.completed)
    return HttpResponse(status=200)

