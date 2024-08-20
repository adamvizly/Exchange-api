from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from .models import UserBalance, TokenPrice, Order

class TokenExchangeViewTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='testuser1', password='testpass')
        self.user2 = User.objects.create_user(username='testuser2', password='testpass')
        
        # Create user balances
        UserBalance.objects.create(user=self.user1, balance=Decimal('100.00'))
        UserBalance.objects.create(user=self.user2, balance=Decimal('100.00'))
        
        # Create some token prices
        TokenPrice.objects.create(token_name='BTC', price=Decimal('10.00'))
        TokenPrice.objects.create(token_name='ETH', price=Decimal('5.00'))
        TokenPrice.objects.create(token_name='ABAN', price=Decimal('4.00'))

    def test_successful_order(self):
        self.client.force_authenticate(user=self.user1)
        data = {'token_name': 'BTC', 'amount': '2.0'}
        response = self.client.post('/api/exchange/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['success'], 'Order placed successfully')
        
        # Check if the balance was updated correctly
        user_balance = UserBalance.objects.get(user=self.user1)
        self.assertEqual(user_balance.balance, Decimal('80.00'))
        
        # Check if the order was created
        order = Order.objects.filter(user=self.user1).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.token_name, 'BTC')
        self.assertEqual(order.amount, Decimal('2.0'))

    def test_insufficient_balance(self):
        self.client.force_authenticate(user=self.user1)
        data = {'token_name': 'BTC', 'amount': '20.0'}
        response = self.client.post('/api/exchange/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Insufficient balance')

    def test_invalid_token(self):
        self.client.force_authenticate(user=self.user1)
        data = {'token_name': 'INVALID', 'amount': '1.0'}
        response = self.client.post('/api/exchange/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid token name')

    def test_buy_from_exchange_trigger(self):
        # This test will place multiple orders from different users to trigger buy_from_exchange
        self.client.force_authenticate(user=self.user1)
        data1 = {'token_name': 'ABAN', 'amount': '1.0'}
        response = self.client.post('/api/exchange/', data1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.user2)
        data2 = {'token_name': 'ABAN', 'amount': '1.0'}
        response = self.client.post('/api/exchange/', data2)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Place one more order to trigger buy_from_exchange
        response = self.client.post('/api/exchange/', data2)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if all orders are marked as included_in_exchange
        orders = Order.objects.filter(token_name='ABAN')
        self.assertEqual(orders.count(), 3)
        self.assertTrue(all(order.included_in_exchange for order in orders))

        # Check balances
        balance1 = UserBalance.objects.get(user=self.user1)
        balance2 = UserBalance.objects.get(user=self.user2)
        self.assertEqual(balance1.balance, Decimal('96.00'))  
        self.assertEqual(balance2.balance, Decimal('92.00'))

    def test_unauthenticated_request(self):
        self.client.force_authenticate(user=None)
        data = {'token_name': 'BTC', 'amount': '1.0'}
        response = self.client.post('/api/exchange/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_multiple_orders_without_trigger(self):
        self.client.force_authenticate(user=self.user1)
        data = {'token_name': 'ETH', 'amount': '0.5'}
        
        # Place two orders that sum up to less than $10
        for _ in range(2):
            response = self.client.post('/api/exchange/', data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if orders are not marked as included_in_exchange
        orders = Order.objects.all()
        self.assertEqual(orders.count(), 2)
        self.assertFalse(any(order.included_in_exchange for order in orders))

    def test_exact_trigger_amount(self):
        self.client.force_authenticate(user=self.user1)
        data = {'token_name': 'BTC', 'amount': '1.0'}
        
        # Place an order for exactly $10
        response = self.client.post('/api/exchange/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if the order is marked as included_in_exchange
        order = Order.objects.first()
        self.assertTrue(order.included_in_exchange)
