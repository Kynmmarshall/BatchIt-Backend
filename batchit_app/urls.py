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
    path('auth/refresh/', views.RefreshTokenView.as_view(), name='auth-refresh'),
    path('auth/update-profile/', views.UpdateProfileView.as_view(), name='auth-update-profile'),
    path('auth/send-verification-code/', views.SendVerificationCodeView.as_view(), name='send-verification-code'),
    path('auth/verify-email-code/', views.VerifyEmailCodeView.as_view(), name='verify-email-code'),
    path('auth/register-verify/', views.RegisterWithVerificationView.as_view(), name='register-verify'),
    path('auth/google-login/', views.GoogleLoginView.as_view(), name='auth-google-login'),

    # Customer URLs
    path('customers/', views.CustomerListCreate.as_view(), name='customer-list-create'),
    path('customers/<uuid:customer_id>/', views.CustomerDetail.as_view(), name='customer-detail'),

    # Provider URLs — my-profile must come before the detail pattern
    path('providers/', views.ProviderListCreate.as_view(), name='provider-list-create'),
    path('providers/my-profile/', views.ProviderMyProfileView.as_view(), name='provider-my-profile'),
    path('providers/register/', views.ProviderRegisterView.as_view(), name='provider-register'),
    path('providers/<uuid:provider_id>/', views.ProviderDetail.as_view(), name='provider-detail'),

    # Product URLs
    path('products/', views.ProductListCreate.as_view(), name='product-list-create'),
    path('products/<uuid:product_id>/', views.ProductDetail.as_view(), name='product-detail'),

    # Batch URLs
    path('batches/', views.BatchListCreate.as_view(), name='batch-list-create'),
    path('batches/<uuid:batch_id>/', views.BatchDetail.as_view(), name='batch-detail'),
    path('batches/<uuid:batch_id>/join/', views.BatchJoinView.as_view(), name='batch-join'),

    # Order URLs (backed by BatchParticipant)
    path('orders/', views.OrderListCreate.as_view(), name='order-list-create'),
    path('orders/<uuid:order_id>/', views.OrderDetail.as_view(), name='order-detail'),

    # BatchParticipant URLs
    path('batch-participants/', views.BatchParticipantListCreate.as_view(), name='batchparticipant-list-create'),
    path('batch-participants/<uuid:participant_id>/', views.BatchParticipantDetail.as_view(), name='batchparticipant-detail'),

    # Subscription URLs
    path('subscriptions/', views.SubscriptionListCreate.as_view(), name='subscription-list-create'),
    path('subscriptions/<uuid:subscription_id>/', views.SubscriptionDetail.as_view(), name='subscription-detail'),

    # Batch extended — edit/delete, pricing, notify participants, chat
    path('batches/<uuid:batch_id>/edit/', views.BatchEditDeleteView.as_view(), name='batch-edit-delete'),
    path('batches/<uuid:batch_id>/pricing/', views.BatchPricingView.as_view(), name='batch-pricing'),
    path('batches/<uuid:batch_id>/notify/', views.ProviderNotifyParticipantsView.as_view(), name='batch-notify'),
    path('batches/<uuid:batch_id>/chat/', views.BatchChatRoomView.as_view(), name='batch-chat-room'),
    path('batches/<uuid:batch_id>/chat/messages/', views.ChatMessageListCreate.as_view(), name='batch-chat-messages'),

    # Admin — provider verification
    path('admin/providers/', views.AdminProviderListView.as_view(), name='admin-provider-list'),
    path('admin/providers/<uuid:provider_id>/verify/', views.AdminProviderVerifyView.as_view(), name='admin-provider-verify'),

    # Provider — follow / unfollow / list followed
    path('providers/followed/', views.FollowedProvidersView.as_view(), name='provider-followed'),
    path('providers/<uuid:provider_id>/follow/', views.FollowProviderView.as_view(), name='provider-follow'),

    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('notifications/<uuid:notif_id>/', views.NotificationDetailView.as_view(), name='notification-detail'),

    # User settings
    path('settings/', views.UserSettingsView.as_view(), name='user-settings'),
]
