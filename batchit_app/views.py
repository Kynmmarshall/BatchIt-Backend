import os
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
from google.auth.transport import requests
from google.oauth2 import id_token
from .models import Customer, Provider, Product, Batch, BatchParticipant, Subscription, EmailVerificationCode
from .serializers import (
    CustomerSerializer, ProviderSerializer, ProviderRegisterSerializer,
    ProductSerializer, BatchSerializer, BatchCreateSerializer,
    BatchParticipantSerializer, SubscriptionSerializer,
    LoginSerializer, RegisterSerializer, AuthDetailSerializer,
    OrderSerializer, OrderCreateSerializer, OrderStatusUpdateSerializer,
    JoinBatchSerializer, SendVerificationCodeSerializer, VerifyEmailCodeSerializer,
    RegisterWithVerificationSerializer, GoogleLoginSerializer,
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
    pagination_class = None

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
class BatchListCreate(APIView):
    """
    GET /api/batches/  — list open batches (optionally filtered by status or location)
    POST /api/batches/ — create a new batch
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        qs = Batch.objects.select_related('provider').all()
        status_filter = request.query_params.get('status')
        location_filter = request.query_params.get('location')
        creator_filter = request.query_params.get('creator')

        if creator_filter == 'me' and request.user.is_authenticated:
            qs = qs.filter(creator=request.user)
            logger.info('[BatchListCreate.get] creator=me filter for user=%s', request.user.email)
        elif status_filter:
            qs = qs.filter(status=status_filter)
            logger.debug('[BatchListCreate.get] status filter=%s', status_filter)
        else:
            qs = qs.filter(status='open')

        if location_filter:
            qs = qs.filter(location_name__icontains=location_filter)

        serializer = BatchSerializer(qs, many=True)
        logger.info('[BatchListCreate.get] returning %d batches (user=%s)', len(serializer.data), getattr(request.user, 'email', 'anon'))
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        logger.info('[BatchListCreate.post] user=%s data=%s files=%s', request.user.email, dict(request.data), list(request.FILES.keys()))
        serializer = BatchCreateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('[BatchListCreate.post] validation errors=%s', serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        provider = None
        provider_id = data.get('provider_id')
        if provider_id:
            try:
                import uuid as _uuid_mod
                provider = Provider.objects.filter(provider_id=_uuid_mod.UUID(str(provider_id))).first()
                if not provider:
                    logger.warning('[BatchListCreate.post] provider_id=%s not found, continuing without provider', provider_id)
            except (ValueError, AttributeError):
                logger.warning('[BatchListCreate.post] provider_id=%s is not a valid UUID, skipping', provider_id)

        # Find or create a Product under this provider for the given name
        product = None
        if provider:
            existing = Product.objects.filter(
                provider=provider,
                name__iexact=data['product_name'],
            ).first()
            if existing:
                product = existing
            else:
                product = Product.objects.create(
                    provider=provider,
                    name=data['product_name'],
                    pack_size=1,
                    pack_price=0,
                )

        # Handle optional image file upload
        image_url = data.get('image_url')
        image_file = request.FILES.get('image')
        if image_file:
            import uuid as _uuid
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'batch_images')
            os.makedirs(upload_dir, exist_ok=True)
            ext = os.path.splitext(image_file.name)[1]
            filename = f'{_uuid.uuid4()}{ext}'
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, 'wb+') as f:
                for chunk in image_file.chunks():
                    f.write(chunk)
            image_url = request.build_absolute_uri(
                settings.MEDIA_URL + f'batch_images/{filename}'
            )

        batch = Batch.objects.create(
            creator=request.user,
            product=product,
            provider=provider,
            product_name=data['product_name'],
            total_quantity=data['total_quantity'],
            filled_quantity=0,
            location_name=data.get('location', ''),
            notes=data.get('notes', ''),
            image_url=image_url,
            expires_at=data.get('expires_at'),
        )
        logger.info('[BatchListCreate.post] created batch id=%s product=%s user=%s', batch.batch_id, batch.product_name, request.user.email)
        return Response(BatchSerializer(batch).data, status=status.HTTP_201_CREATED)

class BatchDetail(generics.RetrieveUpdateDestroyAPIView):
    """Retrieves, updates, or deletes a specific batch."""
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    lookup_field = 'batch_id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


def _join_batch_for_customer(*, batch, customer, quantity_kg):
    """
    Shared join/order logic used by /orders/ and /batches/<id>/join/.
    Ensures batch is open, capacity is respected, and filled/status are updated atomically.
    """
    if batch.status != 'open':
        raise ValidationError({'detail': 'This batch is not open for joining.'})

    with transaction.atomic():
        batch = Batch.objects.select_for_update().get(batch_id=batch.batch_id)

        currently_filled = (
            BatchParticipant.objects
            .filter(batch=batch)
            .aggregate(total=Sum('quantity_requested'))['total']
            or 0
        )

        remaining = batch.total_quantity - currently_filled
        if quantity_kg > remaining:
            raise ValidationError({
                'quantity_kg': f'Only {remaining} kg remaining in this batch.'
            })

        existing = BatchParticipant.objects.filter(batch=batch, customer=customer).first()
        if existing:
            existing.quantity_requested += quantity_kg
            existing.save(update_fields=['quantity_requested'])
            participant = existing
        else:
            participant = BatchParticipant.objects.create(
                batch=batch,
                customer=customer,
                quantity_requested=quantity_kg,
            )

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
        logger.info('[BatchJoinView.post] user=%s batch_id=%s data=%s', request.user.email, batch_id, request.data)
        serializer = JoinBatchSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('[BatchJoinView.post] validation errors=%s', serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        batch = generics.get_object_or_404(Batch, batch_id=batch_id)
        participant = _join_batch_for_customer(
            batch=batch,
            customer=request.user,
            quantity_kg=serializer.validated_data['quantity_requested'],
        )
        logger.info('[BatchJoinView.post] joined batch=%s qty=%s user=%s', batch_id, serializer.validated_data['quantity_requested'], request.user.email)
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
        logger.info('[OrderListCreate.get] user=%s', request.user.email)
        queryset = BatchParticipant.objects.filter(customer=request.user).select_related(
            'batch', 'batch__product', 'batch__provider'
        )
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        serializer = OrderSerializer(queryset, many=True)
        logger.info('[OrderListCreate.get] returning %d orders for user=%s', len(serializer.data), request.user.email)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        logger.info('[OrderListCreate.post] user=%s data=%s', request.user.email, request.data)
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('[OrderListCreate.post] validation errors=%s', serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        batch = generics.get_object_or_404(Batch, batch_id=serializer.validated_data['batch_id'])
        participant = _join_batch_for_customer(
            batch=batch,
            customer=request.user,
            quantity_kg=serializer.validated_data['quantity_requested'],
        )
        logger.info('[OrderListCreate.post] joined batch=%s qty=%s user=%s', batch.batch_id, serializer.validated_data['quantity_requested'], request.user.email)
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
        logger.info('[OrderDetail.patch] user=%s order_id=%s data=%s', request.user.email, order_id, request.data)
        participant = self._get_object(order_id, request.user)
        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'status' in data:
            participant.status = data['status']
            participant.save(update_fields=['status'])

        if 'quantity_kg' in data:
            new_qty = data['quantity_kg']
            with transaction.atomic():
                batch = Batch.objects.select_for_update().get(batch_id=participant.batch.batch_id)
                old_qty = participant.quantity_requested
                available = batch.total_quantity - (batch.filled_quantity - old_qty)
                if new_qty > available:
                    raise ValidationError({'quantity_kg': f'Only {available} kg available in this batch.'})
                participant.quantity_requested = new_qty
                participant.save(update_fields=['quantity_requested'])
                batch.filled_quantity = batch.filled_quantity - old_qty + new_qty
                batch.status = 'filled' if batch.filled_quantity >= batch.total_quantity else 'open'
                batch.save(update_fields=['filled_quantity', 'status'])
                logger.info('[OrderDetail.patch] qty updated order=%s old=%s new=%s', order_id, old_qty, new_qty)

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
            logger.info('Successful login for user: %s', user.email)
            return Response({
                'token': token.key,
                'user': AuthDetailSerializer(user).data,
            }, status=status.HTTP_200_OK)
        logger.warning('Failed login attempt: %s; request email: %s', serializer.errors, request.data.get('email', 'N/A'))
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


class GoogleLoginView(APIView):
    """
    POST /api/auth/google-login/
    Login or register with Google OAuth.
    Accepts Google ID token, validates it, creates/authenticates user, returns auth token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token_str = serializer.validated_data['id_token']

        try:
            # Verify the ID token using Google's public keys
            # Note: This uses the new google-auth library API
            request_obj = requests.Request()
            # Get Google's current public keys
            from google.oauth2 import id_token as id_token_module
            
            # Verify the token (this will raise an exception if invalid)
            id_info = id_token.verify_oauth2_token(
                id_token_str,
                request_obj,
                clock_skew_in_seconds=10,
            )

            # Extract user info from token
            email = id_info.get('email')
            first_name = id_info.get('given_name', '')
            last_name = id_info.get('family_name', '')
            google_id = id_info.get('sub')  # Subject (unique Google ID)

            if not email:
                return Response(
                    {'detail': 'Email not found in Google token.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create or get user account
            user, created = Customer.objects.get_or_create(
                email=email,
                defaults={
                    'username': email.split('@')[0] + '_' + google_id[:8],  # Create unique username
                    'first_name': first_name,
                    'last_name': last_name,
                }
            )

            # Set a random password for Google-authenticated users (they don't use password login)
            if created:
                user.set_unusable_password()
                user.save()
                logger.info('Created new user from Google login: %s', email)
            else:
                logger.info('Authenticated existing user via Google: %s', email)

            # Generate or get auth token
            token, _ = Token.objects.get_or_create(user=user)

            return Response({
                'token': token.key,
                'user': AuthDetailSerializer(user).data,
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            # Token validation failed
            logger.warning('Invalid Google ID token: %s', str(e))
            return Response(
                {'detail': f'Invalid Google token: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Other errors
            logger.exception('Google login error: %s', str(e))
            return Response(
                {'detail': f'Google login failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RefreshTokenView(APIView):
    """
    POST /api/auth/refresh/
    Refreshes the auth token by deleting the old one and issuing a new one.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        token = Token.objects.create(user=request.user)
        return Response({'token': token.key}, status=status.HTTP_200_OK)


class UpdateProfileView(APIView):
    """
    PATCH /api/auth/update-profile/
    Updates the authenticated user's first_name, last_name, and optionally profile_photo.
    Accepts multipart/form-data when a photo file is included.
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        logger.info('[UpdateProfileView.patch] user=%s fields=%s has_photo=%s', request.user.email, list(request.data.keys()), 'photo' in request.FILES)
        user = request.user
        first_name = request.data.get('first_name', user.first_name)
        last_name = request.data.get('last_name', user.last_name)

        user.first_name = first_name
        user.last_name = last_name

        photo = request.FILES.get('photo')
        if photo:
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'profile_photos')
            os.makedirs(upload_dir, exist_ok=True)
            ext = os.path.splitext(photo.name)[1]
            filename = f'{user.customer_id}{ext}'
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, 'wb+') as f:
                for chunk in photo.chunks():
                    f.write(chunk)
            user.profile_photo_url = request.build_absolute_uri(
                settings.MEDIA_URL + f'profile_photos/{filename}'
            )

        user.save(update_fields=['first_name', 'last_name', 'profile_photo_url'])
        return Response(AuthDetailSerializer(user).data, status=status.HTTP_200_OK)


class ProviderMyProfileView(APIView):
    """
    GET /api/providers/my-profile/
    Returns the provider profile owned by the authenticated user (matched by owner_email).
    Returns 404 if the user hasn't registered as a provider yet.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        provider = Provider.objects.filter(owner_email=request.user.email).first()
        if not provider:
            return Response({'detail': 'No provider profile found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProviderSerializer(provider).data, status=status.HTTP_200_OK)


class ProviderRegisterView(APIView):
    """
    POST /api/providers/register/
    Creates a new provider profile for the authenticated user.
    Accepts multipart/form-data so a logo image can be uploaded.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logger.info('[ProviderRegisterView.post] user=%s data=%s files=%s', request.user.email, dict(request.data), list(request.FILES.keys()))
        # Prevent duplicate provider registration
        if Provider.objects.filter(owner_email=request.user.email).exists():
            return Response(
                {'detail': 'You have already registered as a provider.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProviderRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('[ProviderRegisterView.post] validation errors=%s', serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        logo_url = None
        logo = request.FILES.get('logo')
        if logo:
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'provider_logos')
            os.makedirs(upload_dir, exist_ok=True)
            ext = os.path.splitext(logo.name)[1]
            import uuid as _uuid
            filename = f'{_uuid.uuid4()}{ext}'
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, 'wb+') as f:
                for chunk in logo.chunks():
                    f.write(chunk)
            logo_url = request.build_absolute_uri(
                settings.MEDIA_URL + f'provider_logos/{filename}'
            )

        provider = Provider.objects.create(
            business_name=data['business_name'],
            description=data.get('description', ''),
            category=data.get('category', ''),
            contact_email=data.get('email', request.user.email),
            owner_name=data.get('owner_name', ''),
            owner_email=request.user.email,
            phone=data.get('phone', ''),
            address=data.get('address', ''),
            registration_number=data.get('registration_number', ''),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            location=data.get('location', ''),
            logo_url=logo_url,
            status='pending',
        )
        logger.info('[ProviderRegisterView.post] created provider id=%s name=%s for user=%s', provider.provider_id, provider.business_name, request.user.email)
        return Response(ProviderSerializer(provider).data, status=status.HTTP_201_CREATED)
