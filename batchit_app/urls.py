from django.urls import path, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from . import views

schema_view = get_schema_view(
    openapi.Info(
        title="Batchit API",
        default_version='v1',
        description="API documentation for the Batchit platform",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('', views.ApiRootView.as_view(), name='api-root'),

    # Swagger/OpenAPI documentation
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Auth URLs
    path('auth/login/', views.LoginView.as_view(), name='auth-login'),
    path('auth/register/', views.RegisterView.as_view(), name='auth-register'),
    path('auth/logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', views.MeView.as_view(), name='auth-me'),

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
