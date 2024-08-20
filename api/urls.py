from django.urls import path
from .views import TokenExchangeView

urlpatterns = [
    path('exchange/', TokenExchangeView.as_view(), name='token_exchange'),
]
