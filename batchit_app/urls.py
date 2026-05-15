from django.urls import path, include
from . import views

urlpatterns = [
    # Customer URLs
    path('customers/', views.CustomerListCreate.as_view(), name='customer-list-create'),
    path('customers/<uuid:pk>/', views.CustomerDetail.as_view(), name='customer-detail'),

    # Provider URLs
    path('providers/', views.ProviderListCreate.as_view(), name='provider-list-create'),
    path('providers/<uuid:pk>/', views.ProviderDetail.as_view(), name='provider-detail'),

    # Product URLs
    path('products/', views.ProductListCreate.as_view(), name='product-list-create'),
    path('products/<uuid:pk>/', views.ProductDetail.as_view(), name='product-detail'),

    # Batch URLs
    path('batches/', views.BatchListCreate.as_view(), name='batch-list-create'),
    path('batches/<uuid:pk>/', views.BatchDetail.as_view(), name='batch-detail'),

    # BatchParticipant URLs
    path('batch-participants/', views.BatchParticipantListCreate.as_view(), name='batchparticipant-list-create'),
    path('batch-participants/<uuid:pk>/', views.BatchParticipantDetail.as_view(), name='batchparticipant-detail'),

    # Subscription URLs
    path('subscriptions/', views.SubscriptionListCreate.as_view(), name='subscription-list-create'),
    path('subscriptions/<uuid:pk>/', views.SubscriptionDetail.as_view(), name='subscription-detail'),
]