import stripe

import json

from django.shortcuts import render, redirect
from django.conf import settings
from django.http import  JsonResponse
from django.views import View
from django.views.generic import TemplateView


stripe.api_key = settings.STRIPE_SECRET_KEY  # The Stripe API uses API keys to authenticate requests.


"""
> All API requests must be made over HTTPS. Calls made over plain HTTP will fail. 
  API requests without authentication will also fail
"""


class Donation_landing_page(View):
    def get(self, request):
      context = {
          'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY
      }
      return render(request, 'payments/checkout.html', context) 



class CreateDonationCheckoutSession(View):
   def post(self, request, *args, **kwargs):
        
        # To get dynamic amount from user, 
        data = json.loads(request.body) # Will accept a dynamic amount (via request.body JSON),
        amount = int(data.get("amount", 0))  
        if amount <= 0:
            return JsonResponse({"error": "Invalid amount"}, status=400)

        YOUR_DOMAIN = "http://127.0.0.1:8000"
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': (amount * 100),
                    'product_data': {
                        'name': 'Donation to keep alive this Blog ❤️',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            metadata={
                "purpose": "blog_donation"
            },
            success_url=YOUR_DOMAIN + '/payments/success/',
            cancel_url=YOUR_DOMAIN + '/payments/cancel/',
        )

        return JsonResponse(
            {
                'id': session.id
            })
            

class Success(TemplateView):
    template_name = 'payments/success.html'

class Cancel(TemplateView):
    template_name = 'payments/cancel.html'


