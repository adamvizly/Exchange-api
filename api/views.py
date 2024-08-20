from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import UserBalance, Order, TokenPrice
from decimal import Decimal
from django.db.models import Sum, F

class TokenExchangeView(APIView):
    @transaction.atomic
    def post(self, request):
        token_name = request.data.get('token_name')
        amount = Decimal(request.data.get('amount'))
        user = request.user

        try:
            token_price = TokenPrice.objects.get(token_name=token_name)
        except TokenPrice.DoesNotExist:
            return Response({"error": "Invalid token name"}, status=status.HTTP_400_BAD_REQUEST)

        total_price = token_price.price * amount

        user_balance, created = UserBalance.objects.get_or_create(user=user)
        if user_balance.balance < total_price:
            return Response({"error": "Insufficient balance"}, status=status.HTTP_400_BAD_REQUEST)

        user_balance.balance -= total_price
        user_balance.save()

        new_order = Order.objects.create(
            user=user, 
            token_name=token_name, 
            amount=amount,
            price=token_price.price
        )

        # Check if total order value reaches $10
        self.check_and_execute_exchange()

        return Response({"success": "Order placed successfully"}, status=status.HTTP_200_OK)

    def check_and_execute_exchange(self):
        # Get all orders that haven't been included in an exchange
        pending_orders = Order.objects.filter(included_in_exchange=False)

        # Calculate the total value of pending orders
        total_value = pending_orders.aggregate(
            total=Sum(F('amount') * F('price'))
        )['total'] or Decimal('0')

        if total_value >= 10:
            self.buy_from_exchange(pending_orders)

    def buy_from_exchange(self, orders):
        print("Buying from exchange")

        orders.update(included_in_exchange=True)
