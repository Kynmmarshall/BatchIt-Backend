from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.core.mail import send_mail
from django.conf import settings
import logging
from .models import Customer, Provider, Product, Batch, BatchParticipant, Subscription, EmailVerificationCode
from .serializers import (
    CustomerSerializer, ProviderSerializer, ProductSerializer,
    BatchSerializer, BatchParticipantSerializer, SubscriptionSerializer,
    LoginSerializer, RegisterSerializer, AuthDetailSerializer,
    OrderSerializer, OrderCreateSerializer, OrderStatusUpdateSerializer,
    JoinBatchSerializer, SendVerificationCodeSerializer, VerifyEmailCodeSerializer,
    RegisterWithVerificationSerializer,
)


logger = logging.getLogger(__name__)


class ApiRootView(APIView):
    """
    GET /api/
    Lightweight API root endpoint used for health and discoverability.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            'name': 'BatchIt API',
            'status': 'ok',
            'docs': '/api/swagger/',
            'version': 'v1',
        }, status=status.HTTP_200_OK)


# --- Customer Views ---
class CustomerListCreate(generics.ListCreateAPIView):
    """Lists all customers or creates a new customer."""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Adjust permissions as needed

    def perform_create(self, serializer):
        # For customer creation, you might want to handle password hashing and other auth details
        # For now, we assume basic fields are set and email is used as username.
        serializer.save()

class CustomerDetail(generics.RetrieveUpdateDestroyAPIView):
    """Retrieves, updates, or deletes a specific customer."""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    lookup_field = 'customer_id' # Assuming customer_id is the PK
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# --- Provider Views ---
class ProviderListCreate(generics.ListCreateAPIView):
    """Lists all providers or creates a new provider."""
    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ProviderDetail(generics.RetrieveUpdateDestroyAPIView):
    """Retrieves, updates, or deletes a specific provider."""
    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer
    lookup_field = 'provider_id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# --- Product Views ---
class ProductListCreate(generics.ListCreateAPIView):
    """Lists all products or creates a new product."""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ProductDetail(generics.RetrieveUpdateDestroyAPIView):
    """Retrieves, updates, or deletes a specific product."""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'product_id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# --- Batch Views ---
class BatchListCreate(generics.ListCreateAPIView):
    """Lists all batches or creates a new batch."""
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        # Set the creator to the currently logged-in user
        serializer.save(creator=self.request.user)

class BatchDetail(generics.RetrieveUpdateDestroyAPIView):
    """Retrieves, updates, or deletes a specific batch."""
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    lookup_field = 'batch_id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


def _join_batch_for_customer(*, batch, customer, quantity_requested):
    """
    Shared join/order logic used by /orders/ and /batches/<id>/join/.
    Ensures batch is open, capacity is respected, and filled/status are updated.
    """
    if batch.status != 'open':
        raise ValidationError({'detail': 'This batch is not open for joining.'})

    if quantity_requested <= 0:
        raise ValidationError({'quantity_requested': 'Quantity must be greater than zero.'})

    with transaction.atomic():
        batch = Batch.objects.select_for_update().get(batch_id=batch.batch_id)

        currently_filled = (
            BatchParticipant.objects
            .filter(batch=batch)
            .aggregate(total=Sum('quantity_requested'))['total']
            or 0
        )

        remaining = batch.total_quantity - currently_filled
        if quantity_requested > remaining:
            raise ValidationError({
                'quantity_requested': f'Only {remaining} unit(s) remaining in this batch.'
            })

        participant, created = BatchParticipant.objects.get_or_create(
            batch=batch,
            customer=customer,
            defaults={'quantity_requested': quantity_requested},
        )

        if not created:
            participant.quantity_requested += quantity_requested
            participant.save(update_fields=['quantity_requested'])

        refreshed_filled = (
            BatchParticipant.objects
            .filter(batch=batch)
            .aggregate(total=Sum('quantity_requested'))['total']
            or 0
        )
        batch.filled_quantity = refreshed_filled
        batch.status = 'filled' if refreshed_filled >= batch.total_quantity else 'open'
        batch.save(update_fields=['filled_quantity', 'status'])

    return participant


class BatchJoinView(APIView):
    """
    POST /api/batches/<id>/join/
    Join an existing batch.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, batch_id):
        serializer = JoinBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        batch = generics.get_object_or_404(Batch, batch_id=batch_id)
        participant = _join_batch_for_customer(
            batch=batch,
            customer=request.user,
            quantity_requested=serializer.validated_data['quantity_requested'],
        )
        return Response(OrderSerializer(participant).data, status=status.HTTP_201_CREATED)

# --- BatchParticipant Views ---
class BatchParticipantListCreate(generics.ListCreateAPIView):
    """Lists all batch participants or creates a new batch participant."""
    queryset = BatchParticipant.objects.all()
    serializer_class = BatchParticipantSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        # Ensure the customer joining is the current user
        serializer.save(customer=self.request.user)

class BatchParticipantDetail(generics.RetrieveUpdateDestroyAPIView):
    """Retrieves, updates, or deletes a specific batch participant."""
    queryset = BatchParticipant.objects.all()
    serializer_class = BatchParticipantSerializer
    lookup_field = 'participant_id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

# --- Subscription Views ---
class SubscriptionListCreate(generics.ListCreateAPIView):
    """Lists all subscriptions or creates a new subscription."""
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        # Ensure the customer subscribing is the current user
        serializer.save(customer=self.request.user)

class SubscriptionDetail(generics.RetrieveUpdateDestroyAPIView):
    """Retrieves, updates, or deletes a specific subscription."""
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    lookup_field = 'subscription_id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


# --- Order Views (backed by BatchParticipant) ---

class OrderListCreate(APIView):
    """
    GET /api/orders/
    POST /api/orders/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = BatchParticipant.objects.filter(customer=request.user).select_related(
            'batch', 'batch__product', 'batch__provider'
        )
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        serializer = OrderSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        batch = generics.get_object_or_404(Batch, batch_id=serializer.validated_data['batch_id'])
        participant = _join_batch_for_customer(
            batch=batch,
            customer=request.user,
            quantity_requested=serializer.validated_data['quantity_requested'],
        )
        return Response(OrderSerializer(participant).data, status=status.HTTP_201_CREATED)


class OrderDetail(APIView):
    """
    GET /api/orders/<id>/
    PATCH /api/orders/<id>/
    DELETE /api/orders/<id>/
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_object(self, order_id, user):
        return generics.get_object_or_404(
            BatchParticipant.objects.select_related('batch', 'batch__product', 'batch__provider'),
            participant_id=order_id,
            customer=user,
        )

    def get(self, request, order_id):
        participant = self._get_object(order_id, request.user)
        return Response(OrderSerializer(participant).data, status=status.HTTP_200_OK)

    def patch(self, request, order_id):
        participant = self._get_object(order_id, request.user)
        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant.status = serializer.validated_data['status']
        participant.save(update_fields=['status'])
        return Response(OrderSerializer(participant).data, status=status.HTTP_200_OK)

    def delete(self, request, order_id):
        participant = self._get_object(order_id, request.user)
        batch = participant.batch
        participant.delete()

        refreshed_filled = (
            BatchParticipant.objects
            .filter(batch=batch)
            .aggregate(total=Sum('quantity_requested'))['total']
            or 0
        )
        batch.filled_quantity = refreshed_filled
        if batch.status == 'filled' and refreshed_filled < batch.total_quantity:
            batch.status = 'open'
        batch.save(update_fields=['filled_quantity', 'status'])

        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Email Verification Views ---

class SendVerificationCodeView(APIView):
    """
    POST /api/auth/send-verification-code/
    Send a 6-digit verification code to the provided email.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SendVerificationCodeSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as ve:
            logger.warning('Validation error in send-verification-code: %s; request: %s', ve.detail if hasattr(ve, 'detail') else str(ve), request.data)
            return Response(ve.detail if hasattr(ve, 'detail') else {'detail': str(ve)}, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']

        # Check if email already registered
        if Customer.objects.filter(email=email).exists():
            return Response(
                {'detail': 'Email already registered.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate and save verification code
        code = EmailVerificationCode.generate_code()
        verification = EmailVerificationCode.objects.create(
            email=email,
            code=code,
        )

        # Validate SMTP configuration before attempting to send.
        backend = (settings.EMAIL_BACKEND or '').strip()
        host = (settings.EMAIL_HOST or '').strip()
        host_user = (settings.EMAIL_HOST_USER or '').strip()
        host_password = (settings.EMAIL_HOST_PASSWORD or '').strip()
        configured_from = (settings.DEFAULT_FROM_EMAIL or '').strip()
        from_email = configured_from or host_user

        if backend != 'django.core.mail.backends.smtp.EmailBackend':
            verification.delete()
            return Response(
                {
                    'detail': (
                        'Email service is not configured for SMTP. '
                        'Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend in your .env and restart service.'
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        missing = []
        if not host:
            missing.append('EMAIL_HOST')
        if not host_user:
            missing.append('EMAIL_HOST_USER')
        if not host_password:
            missing.append('EMAIL_HOST_PASSWORD')
        if not from_email:
            missing.append('DEFAULT_FROM_EMAIL or EMAIL_HOST_USER')

        if missing:
            verification.delete()
            return Response(
                {
                    'detail': (
                        'Email service is missing required settings: '
                        + ', '.join(missing)
                        + '. Update .env and restart service.'
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Send email with verification code
        try:
            send_mail(
                subject='BatchIt - Email Verification Code',
                message=f'Your verification code is: {code}\n\nThis code will expire in 15 minutes.',
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            logger.exception('Failed to send verification email to %s', email)
            verification.delete()
            return Response(
                {
                    'detail': f'Failed to send verification email: {e.__class__.__name__}: {str(e)}',
                    'email_backend': backend,
                    'email_host': host,
                    'from_email': from_email,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {'detail': f'Verification code sent to {email}'},
            status=status.HTTP_200_OK
        )


class VerifyEmailCodeView(APIView):
    """
    POST /api/auth/verify-email-code/
    Verify the email code (without creating account yet).
    Used for testing or intermediate verification steps.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        try:
            verification = EmailVerificationCode.objects.get(email=email, code=code)
            if not verification.is_valid():
                return Response(
                    {'detail': 'Verification code has expired or already used.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {'detail': 'Verification code is valid.'},
                status=status.HTTP_200_OK
            )
        except EmailVerificationCode.DoesNotExist:
            return Response(
                {'detail': 'Invalid or expired verification code.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class RegisterWithVerificationView(APIView):
    """
    POST /api/auth/register-verify/
    Register a new account with email verification code.
    Verifies the code, creates the account, and returns token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterWithVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'token': token.key,
            'user': AuthDetailSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


# --- Auth Views ---

class LoginView(APIView):
    """
    POST /api/auth/login/
    Login endpoint. Accepts email and password, returns token and user info.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': AuthDetailSerializer(user).data,
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Register endpoint. Accepts email, username, password, and creates a new customer.
    Returns token and user info.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': AuthDetailSerializer(user).data,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Logout endpoint. Deletes the user's token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
            return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    """
    GET /api/auth/me/
    Get current user info. Requires authentication.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = AuthDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
