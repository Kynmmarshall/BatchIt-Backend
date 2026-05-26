import os
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.core.mail import send_mail
from django.conf import settings
from django.http import FileResponse, Http404
import logging
from google.auth.transport import requests
from google.oauth2 import id_token
from .models import (
    Customer, Provider, Product, Batch, BatchParticipant, Subscription,
    EmailVerificationCode, Notification, UserSettings, BatchChatRoom,
    ChatMember, ChatMessage,
)
from .serializers import (
    CustomerSerializer, ProviderSerializer, ProviderRegisterSerializer,
    ProductSerializer, BatchSerializer, BatchCreateSerializer,
    BatchParticipantSerializer, SubscriptionSerializer,
    LoginSerializer, RegisterSerializer, AuthDetailSerializer,
    OrderSerializer, OrderCreateSerializer, OrderStatusUpdateSerializer,
    JoinBatchSerializer, SendVerificationCodeSerializer, VerifyEmailCodeSerializer,
    RegisterWithVerificationSerializer, GoogleLoginSerializer,
    NotificationSerializer, UserSettingsSerializer,
    BatchChatRoomSerializer, ChatMessageSerializer,
    ProviderVerifySerializer, BatchPricingSerializer, ProviderNotifySerializer,
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
        participant_filter = request.query_params.get('participant')

        if creator_filter == 'me' and request.user.is_authenticated:
            qs = qs.filter(creator=request.user)
            logger.info('[BatchListCreate.get] creator=me filter for user=%s', request.user.email)
        elif participant_filter == 'me' and request.user.is_authenticated:
            # Batches the current user has joined (has a BatchParticipant record for).
            joined_ids = BatchParticipant.objects.filter(
                customer=request.user
            ).values_list('batch_id', flat=True)
            qs = qs.filter(batch_id__in=joined_ids)
            logger.info('[BatchListCreate.get] participant=me filter for user=%s, found %d batches', request.user.email, qs.count())
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

        # Handle optional image file upload; if storage fails, create the batch anyway.
        image_url = data.get('image_url')
        image_file = request.FILES.get('image')
        if image_file:
            try:
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
                logger.info('[BatchListCreate.post] stored batch image=%s', image_url)
            except Exception as exc:
                logger.exception('[BatchListCreate.post] image upload failed, continuing without image: %s', exc)
                image_url = data.get('image_url')

        with transaction.atomic():
            batch = Batch.objects.create(
                creator=request.user,
                product=product,
                provider=provider,
                product_name=data['product_name'],
                total_quantity=data['total_quantity'],
                filled_quantity=0,
                unit=data.get('unit', 'kg'),
                status='open',
                location_name=data.get('location', ''),
                notes=data.get('notes', ''),
                image_url=image_url,
                expires_at=data.get('expires_at'),
            )

        # Auto-create chat room and add creator as first member, but do not fail batch creation if it breaks.
        try:
            chat_room = BatchChatRoom.objects.create(batch=batch)
            ChatMember.objects.create(room=chat_room, customer=request.user)
        except Exception as exc:
            logger.exception('[BatchListCreate.post] chat room bootstrap failed for batch=%s: %s', batch.batch_id, exc)

        # Notify all followers of the provider that a new batch is available.
        if provider:
            try:
                subscriber_ids = list(
                    Subscription.objects.filter(provider=provider)
                    .exclude(customer=request.user)
                    .values_list('customer_id', flat=True)
                )
                if subscriber_ids:
                    sub_notifications = [
                        Notification(
                            recipient_id=cid,
                            notification_type='batch_created',
                            title=f'New batch: {batch.product_name}',
                            body=f'{provider.business_name} just created a new batch for {batch.product_name}. Join now before it fills up!',
                            related_batch=batch,
                        )
                        for cid in subscriber_ids
                    ]
                    Notification.objects.bulk_create(sub_notifications)
                    logger.info('[BatchListCreate.post] notified %d subscribers of provider=%s', len(sub_notifications), provider.provider_id)
            except Exception as exc:
                logger.exception('[BatchListCreate.post] subscriber notification failed: %s', exc)

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
            # Auto-join the chat room when joining the batch (Phase 8)
            chat_room = BatchChatRoom.objects.filter(batch=batch).first()
            if chat_room:
                ChatMember.objects.get_or_create(room=chat_room, customer=customer)

        refreshed_filled = (
            BatchParticipant.objects
            .filter(batch=batch)
            .aggregate(total=Sum('quantity_requested'))['total']
            or 0
        )
        batch.filled_quantity = refreshed_filled
        newly_filled = refreshed_filled >= batch.total_quantity
        batch.status = 'filled' if newly_filled else 'open'
        batch.save(update_fields=['filled_quantity', 'status'])

    if batch.creator_id and batch.creator_id != customer.customer_id:
        _notify_batch_joined(batch=batch, participant=participant, customer=customer)

    # Auto-notify all participants when batch just became full (Phase 5)
    if newly_filled:
        _notify_batch_full(batch)

    return participant


def _notify_batch_joined(*, batch, participant, customer):
    """
    Notify the batch creator that someone joined or increased their order.
    """
    creator = batch.creator
    if not creator:
        return

    joined_label = customer.get_full_name().strip() or customer.email
    Notification.objects.create(
        recipient=creator,
        title=f'New join on {batch.product_name}',
        body=f'{joined_label} joined your batch for {batch.product_name} with {participant.quantity_requested} kg.',
        notification_type='batch_joined',
        related_batch=batch,
    )


def _notify_batch_full(batch):
    """
    Create 'batch_full' notifications when a batch reaches capacity.
    Notifies:
      - Every participant: go collect or request delivery.
      - Every subscriber of the provider (not already a participant): batch is ready.
    """
    participants = BatchParticipant.objects.filter(batch=batch).select_related('customer')
    participant_ids = {p.customer_id for p in participants}

    notifications = [
        Notification(
            recipient=p.customer,
            title='Your batch is full — time to collect!',
            body=f'The batch for "{batch.product_name}" is now full. Go collect your order or request delivery.',
            notification_type='batch_full',
            related_batch=batch,
        )
        for p in participants
    ]

    # Also notify provider subscribers who are not already participants.
    if batch.provider_id:
        subscriber_ids = list(
            Subscription.objects.filter(provider_id=batch.provider_id)
            .exclude(customer_id__in=participant_ids)
            .values_list('customer_id', flat=True)
        )
        notifications += [
            Notification(
                recipient_id=sid,
                title=f'Batch full at {batch.provider.business_name}',
                body=f'A "{batch.product_name}" batch at {batch.provider.business_name} just filled up. Contact the provider to join the next one!',
                notification_type='batch_full',
                related_batch=batch,
            )
            for sid in subscriber_ids
        ]

    Notification.objects.bulk_create(notifications)
    logger.info('[_notify_batch_full] created %d notifications for batch=%s', len(notifications), batch.batch_id)


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
            # Issue JWT pair as well for migrating clients
            jwt_refresh = RefreshToken.for_user(user)
            logger.info('Successful login for user: %s', user.email)
            return Response({
                'token': token.key,
                'access': str(jwt_refresh.access_token),
                'refresh': str(jwt_refresh),
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
            jwt_refresh = RefreshToken.for_user(user)
            return Response({
                'token': token.key,
                'access': str(jwt_refresh.access_token),
                'refresh': str(jwt_refresh),
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
        # JWT logout is handled client-side unless refresh token blacklisting is enabled.
        return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)


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

            jwt_refresh = RefreshToken.for_user(user)
            return Response({
                'token': token.key,
                'access': str(jwt_refresh.access_token),
                'refresh': str(jwt_refresh),
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
        jwt_refresh = RefreshToken.for_user(request.user)
        return Response({'access': str(jwt_refresh.access_token), 'refresh': str(jwt_refresh)}, status=status.HTTP_200_OK)


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

        photo = request.FILES.get('photo') or request.FILES.get('profile_photo')
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


class ExchangeTokenView(APIView):
    """
    POST /api/auth/exchange-token/
    Accepts legacy Token auth (via Authorization: Token <token>) and returns a JWT pair for the same user.
    This eases migration from TokenAuthentication to JWT.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Token '):
            return Response({'detail': 'Authorization header with Token required.'}, status=status.HTTP_400_BAD_REQUEST)
        token_key = auth_header.split(' ', 1)[1].strip()
        try:
            token = Token.objects.select_related('user').get(key=token_key)
        except Token.DoesNotExist:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)

        user = token.user
        jwt_refresh = RefreshToken.for_user(user)
        return Response({'access': str(jwt_refresh.access_token), 'refresh': str(jwt_refresh)}, status=status.HTTP_200_OK)


class ProviderMyProfileView(APIView):
    """
    GET /api/providers/my-profile/
    Returns the provider profile owned by the authenticated user (matched by owner_email).
    Returns 404 if the user hasn't registered as a provider yet.

    PATCH /api/providers/my-profile/
    Updates the authenticated provider's profile fields.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        provider = Provider.objects.filter(owner_email=request.user.email).first()
        if not provider:
            return Response({'detail': 'No provider profile found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProviderSerializer(provider, context={'request': request}).data, status=status.HTTP_200_OK)

    def patch(self, request):
        provider = Provider.objects.filter(owner_email=request.user.email).first()
        if not provider:
            return Response({'detail': 'No provider profile found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProviderRegisterSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            logger.warning('[ProviderMyProfileView.patch] validation errors=%s user=%s data=%s', serializer.errors, request.user.email, dict(request.data))
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        update_fields = []

        field_map = {
            'business_name': 'business_name',
            'description': 'description',
            'category': 'category',
            'email': 'contact_email',
            'owner_name': 'owner_name',
            'phone': 'phone',
            'address': 'address',
            'registration_number': 'registration_number',
            'latitude': 'latitude',
            'longitude': 'longitude',
            'location': 'location',
        }

        for source, target in field_map.items():
            if source in data:
                setattr(provider, target, data[source])
                update_fields.append(target)

        # Optional logo update
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
            provider.logo_url = request.build_absolute_uri(settings.MEDIA_URL + f'provider_logos/{filename}')
            update_fields.append('logo_url')

        # Optional document append
        documents = request.FILES.getlist('documents')
        if documents:
            docs_dir = os.path.join(settings.BASE_DIR, 'providerDocs')
            provider_dir = os.path.join(docs_dir, str(provider.provider_id))
            os.makedirs(provider_dir, exist_ok=True)
            stored_paths = list(provider.document_paths or [])
            import uuid as _doc_uuid
            for doc in documents:
                ext = os.path.splitext(doc.name)[1]
                safe_name = f'{_doc_uuid.uuid4()}{ext}'
                absolute_path = os.path.join(provider_dir, safe_name)
                with open(absolute_path, 'wb+') as f:
                    for chunk in doc.chunks():
                        f.write(chunk)
                stored_paths.append(os.path.join(str(provider.provider_id), safe_name).replace('\\', '/'))
            provider.document_paths = stored_paths
            update_fields.append('document_paths')

        if not update_fields:
            return Response({'detail': 'No changes provided.'}, status=status.HTTP_400_BAD_REQUEST)

        provider.save(update_fields=list(set(update_fields)))
        provider.status = 'pending'
        provider.verified = False
        provider.rejection_message = ''
        provider.save(update_fields=['status', 'verified', 'rejection_message'])
        logger.info('[ProviderMyProfileView.patch] updated provider=%s user=%s fields=%s', provider.provider_id, request.user.email, sorted(set(update_fields)))

        _notify_admins_provider_review(
            provider=provider,
            action_label='updated',
            actor_email=request.user.email,
        )
        return Response(ProviderSerializer(provider, context={'request': request}).data, status=status.HTTP_200_OK)


class ProviderRegisterView(APIView):
    """
    POST /api/providers/register/
    Creates a new provider profile for the authenticated user.
    Accepts multipart/form-data so a logo image can be uploaded.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        incoming_keys = sorted(request.data.keys())
        files_meta = {
            key: [
                {
                    'name': f.name,
                    'size': f.size,
                    'content_type': getattr(f, 'content_type', None),
                }
                for f in request.FILES.getlist(key)
            ]
            for key in request.FILES.keys()
        }
        logger.info(
            '[ProviderRegisterView.post] user=%s content_type=%s keys=%s files=%s',
            request.user.email,
            request.content_type,
            incoming_keys,
            files_meta,
        )

        required_fields = {'business_name', 'email'}
        missing_required = sorted(
            field for field in required_fields if not str(request.data.get(field, '')).strip()
        )
        if missing_required:
            logger.warning(
                '[ProviderRegisterView.post] missing required fields=%s user=%s raw_data=%s',
                missing_required,
                request.user.email,
                dict(request.data),
            )

        # Prevent duplicate provider registration
        if Provider.objects.filter(owner_email=request.user.email).exists():
            logger.warning('[ProviderRegisterView.post] duplicate registration attempt user=%s', request.user.email)
            return Response(
                {'detail': 'You have already registered as a provider.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProviderRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                '[ProviderRegisterView.post] validation errors=%s user=%s data=%s',
                serializer.errors,
                request.user.email,
                dict(request.data),
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        logger.info('[ProviderRegisterView.post] validated user=%s fields=%s', request.user.email, sorted(data.keys()))

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
            document_paths=[],
            status='pending',
        )

        documents = request.FILES.getlist('documents')
        if documents:
            docs_dir = os.path.join(settings.BASE_DIR, 'providerDocs')
            provider_dir = os.path.join(docs_dir, str(provider.provider_id))
            os.makedirs(provider_dir, exist_ok=True)
            stored_paths = []
            import uuid as _doc_uuid
            for doc in documents:
                ext = os.path.splitext(doc.name)[1]
                safe_name = f'{_doc_uuid.uuid4()}{ext}'
                absolute_path = os.path.join(provider_dir, safe_name)
                with open(absolute_path, 'wb+') as f:
                    for chunk in doc.chunks():
                        f.write(chunk)
                stored_paths.append(os.path.join(str(provider.provider_id), safe_name).replace('\\', '/'))
            provider.document_paths = stored_paths
            provider.save(update_fields=['document_paths'])
            logger.info('[ProviderRegisterView.post] stored %s documents for provider=%s', len(stored_paths), provider.provider_id)
        else:
            logger.info('[ProviderRegisterView.post] no documents uploaded for provider=%s', provider.provider_id)

        logger.info('[ProviderRegisterView.post] created provider id=%s name=%s for user=%s', provider.provider_id, provider.business_name, request.user.email)

        _notify_admins_provider_review(
            provider=provider,
            action_label='submitted',
            actor_email=request.user.email,
        )
        return Response(ProviderSerializer(provider, context={'request': request}).data, status=status.HTTP_201_CREATED)


def _notify_admins_provider_review(*, provider, action_label, actor_email):
    """
    Notify all staff/superuser accounts that a provider profile needs review.
    """
    admin_ids = list(
        Customer.objects.filter(Q(is_staff=True) | Q(is_superuser=True))
        .values_list('customer_id', flat=True)
    )
    if not admin_ids:
        return

    title = f'Provider profile {action_label} for review'
    body = f'{provider.business_name} was {action_label} by {actor_email} and is waiting for admin review.'

    Notification.objects.bulk_create([
        Notification(
            recipient_id=admin_id,
            title=title,
            body=body,
            notification_type='provider_review',
        )
        for admin_id in admin_ids
    ])


class ProviderDocumentDownloadView(APIView):
    """
    GET /api/providers/<provider_id>/documents/<index>/download/
    Downloads a provider verification document.
    Allowed for admin staff and provider owner.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, provider_id, index):
        provider = Provider.objects.filter(provider_id=provider_id).first()
        if not provider:
            return Response({'detail': 'Provider not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not (request.user.is_staff or provider.owner_email == request.user.email):
            return Response({'detail': 'You do not have permission to access this document.'}, status=status.HTTP_403_FORBIDDEN)

        docs = provider.document_paths or []
        if index < 0 or index >= len(docs):
            return Response({'detail': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

        relative = docs[index]
        docs_root = os.path.join(settings.BASE_DIR, 'providerDocs')
        absolute = os.path.normpath(os.path.join(docs_root, relative))
        normalized_root = os.path.normpath(docs_root)

        if not absolute.startswith(normalized_root):
            raise Http404('Invalid document path.')
        if not os.path.exists(absolute):
            raise Http404('Document file not found.')

        return FileResponse(open(absolute, 'rb'), as_attachment=True, filename=os.path.basename(absolute))


# ---------------------------------------------------------------------------
# Phase 1 — Admin: verify / reject provider
# ---------------------------------------------------------------------------

class AdminProviderListView(APIView):
    """
    GET /api/admin/providers/?status=pending
    List all providers, optionally filtered by status. Admin only.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        qs = Provider.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(ProviderSerializer(qs, many=True, context={'request': request}).data)


class AdminProviderVerifyView(APIView):
    """
    POST /api/admin/providers/<provider_id>/verify/
    Approve or reject a provider. Admin only.
    Body: { "action": "approve" | "reject", "rejection_message": "..." }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider_id):
        if not request.user.is_staff:
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        provider = generics.get_object_or_404(Provider, provider_id=provider_id)
        serializer = ProviderVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data['action'] == 'approve':
            provider.status = 'verified'
            provider.verified = True
            provider.rejection_message = ''
            provider.save(update_fields=['status', 'verified', 'rejection_message'])
            notif_type = 'provider_approved'
            title = 'Provider profile approved!'
            body = f'Congratulations! Your provider profile "{provider.business_name}" has been approved.'
        else:
            provider.status = 'rejected'
            provider.verified = False
            provider.rejection_message = data.get('rejection_message', '')
            provider.save(update_fields=['status', 'verified', 'rejection_message'])
            notif_type = 'provider_rejected'
            title = 'Provider profile rejected'
            body = f'Your provider profile "{provider.business_name}" was rejected. Reason: {provider.rejection_message}'

        # Notify the provider owner
        try:
            owner = Customer.objects.get(email=provider.owner_email)
            Notification.objects.create(
                recipient=owner,
                title=title,
                body=body,
                notification_type=notif_type,
            )
        except Customer.DoesNotExist:
            pass

        logger.info('[AdminProviderVerifyView] provider=%s action=%s by admin=%s', provider_id, data['action'], request.user.email)
        return Response(ProviderSerializer(provider, context={'request': request}).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Phase 2 — Batch edit / delete with ownership checks
# ---------------------------------------------------------------------------

class BatchEditDeleteView(APIView):
    """
    PATCH /api/batches/<batch_id>/edit/
    DELETE /api/batches/<batch_id>/edit/
    Only the creator, assigned provider owner, or admin may modify/delete.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_batch_and_check_permission(self, request, batch_id):
        batch = generics.get_object_or_404(Batch, batch_id=batch_id)
        user = request.user
        is_creator = batch.creator_id == user.customer_id
        is_provider_owner = batch.provider and batch.provider.owner_email == user.email
        if not (is_creator or is_provider_owner or user.is_staff):
            return None, Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return batch, None

    def patch(self, request, batch_id):
        batch, err = self._get_batch_and_check_permission(request, batch_id)
        if err:
            return err

        allowed_fields = {'product_name', 'total_quantity', 'location_name', 'notes', 'expires_at', 'status'}
        update_fields = []
        for field in allowed_fields:
            if field in request.data:
                setattr(batch, field, request.data[field])
                update_fields.append(field)

        image_file = request.FILES.get('image')
        if image_file:
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'batch_images')
            os.makedirs(upload_dir, exist_ok=True)
            ext = os.path.splitext(image_file.name)[1]
            filename = f'{batch.batch_id}{ext}'
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, 'wb+') as f:
                for chunk in image_file.chunks():
                    f.write(chunk)
            batch.image_url = request.build_absolute_uri(
                settings.MEDIA_URL + f'batch_images/{filename}'
            )
            update_fields.append('image_url')

        if update_fields:
            batch.save(update_fields=update_fields)
        return Response(BatchSerializer(batch).data, status=status.HTTP_200_OK)

    def delete(self, request, batch_id):
        batch, err = self._get_batch_and_check_permission(request, batch_id)
        if err:
            return err
        batch.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Phase 3 — Provider sets pricing on a batch
# ---------------------------------------------------------------------------

class BatchPricingView(APIView):
    """
    PATCH /api/batches/<batch_id>/pricing/
    Only the provider assigned to the batch may set pricing.
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, batch_id):
        batch = generics.get_object_or_404(Batch, batch_id=batch_id)
        if not batch.provider or batch.provider.owner_email != request.user.email:
            return Response({'detail': 'Only the assigned provider may set pricing.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = BatchPricingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        batch.provider_unit_price = data['provider_unit_price']
        if 'provider_savings' in data:
            batch.provider_savings = data['provider_savings']
        batch.save(update_fields=['provider_unit_price', 'provider_savings'])
        return Response(BatchSerializer(batch).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Phase 4 — Provider sends notification to all batch participants
# ---------------------------------------------------------------------------

class ProviderNotifyParticipantsView(APIView):
    """
    POST /api/batches/<batch_id>/notify/
    Provider-only: send a custom notification to all batch participants.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, batch_id):
        batch = generics.get_object_or_404(Batch, batch_id=batch_id)
        if not batch.provider or batch.provider.owner_email != request.user.email:
            return Response({'detail': 'Only the assigned provider may send notifications.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProviderNotifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        participants = BatchParticipant.objects.filter(batch=batch).select_related('customer')
        notifications = [
            Notification(
                recipient=p.customer,
                title=data['title'],
                body=data['body'],
                notification_type='provider_message',
                related_batch=batch,
            )
            for p in participants
        ]
        Notification.objects.bulk_create(notifications)
        logger.info('[ProviderNotifyParticipantsView] sent %d notifications for batch=%s', len(notifications), batch_id)
        return Response({'detail': f'Notification sent to {len(notifications)} participant(s).'}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Phase 6 — User settings (language, theme, notification prefs)
# ---------------------------------------------------------------------------

class UserSettingsView(APIView):
    """
    GET  /api/settings/   — return current settings (creates defaults if none)
    PATCH /api/settings/  — update one or more settings fields
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_or_create_settings(self, user):
        obj, _ = UserSettings.objects.get_or_create(customer=user)
        return obj

    def get(self, request):
        settings_obj = self._get_or_create_settings(request.user)
        return Response(UserSettingsSerializer(settings_obj).data, status=status.HTTP_200_OK)

    def patch(self, request):
        settings_obj = self._get_or_create_settings(request.user)
        serializer = UserSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Phase 7 — Follow / unfollow provider; list followed providers
# ---------------------------------------------------------------------------

class FollowProviderView(APIView):
    """
    POST   /api/providers/<provider_id>/follow/   — follow a provider
    DELETE /api/providers/<provider_id>/follow/   — unfollow a provider
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, provider_id):
        provider = generics.get_object_or_404(Provider, provider_id=provider_id)
        _, created = Subscription.objects.get_or_create(customer=request.user, provider=provider)
        if created:
            provider.subscriber_count = Subscription.objects.filter(provider=provider).count()
            provider.save(update_fields=['subscriber_count'])
        return Response({'detail': 'Following.' if created else 'Already following.'}, status=status.HTTP_200_OK)

    def delete(self, request, provider_id):
        provider = generics.get_object_or_404(Provider, provider_id=provider_id)
        deleted, _ = Subscription.objects.filter(customer=request.user, provider=provider).delete()
        if deleted:
            provider.subscriber_count = Subscription.objects.filter(provider=provider).count()
            provider.save(update_fields=['subscriber_count'])
            return Response({'detail': 'Unfollowed.'}, status=status.HTTP_200_OK)
        return Response({'detail': 'Not following.'}, status=status.HTTP_400_BAD_REQUEST)


class FollowedProvidersView(APIView):
    """
    GET /api/providers/followed/
    Returns only the providers the authenticated user follows.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        provider_ids = Subscription.objects.filter(
            customer=request.user
        ).values_list('provider_id', flat=True)
        providers = Provider.objects.filter(provider_id__in=provider_ids)
        return Response(ProviderSerializer(providers, many=True, context={'request': request}).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Phase 8 — Batch chat room: get room info, send/list messages
# ---------------------------------------------------------------------------

class BatchChatRoomView(APIView):
    """
    GET /api/batches/<batch_id>/chat/
    Returns the chat room for a batch (only for participants or the creator).
    """
    permission_classes = [permissions.IsAuthenticated]

    def _check_membership(self, batch, user):
        is_creator = batch.creator_id == user.customer_id
        is_participant = BatchParticipant.objects.filter(batch=batch, customer=user).exists()
        is_provider = batch.provider and batch.provider.owner_email == user.email
        return is_creator or is_participant or is_provider or user.is_staff

    def get(self, request, batch_id):
        batch = generics.get_object_or_404(Batch, batch_id=batch_id)
        if not self._check_membership(batch, request.user):
            return Response({'detail': 'You are not a member of this batch.'}, status=status.HTTP_403_FORBIDDEN)
        chat_room, _ = BatchChatRoom.objects.get_or_create(batch=batch)
        ChatMember.objects.get_or_create(room=chat_room, customer=request.user)
        return Response(BatchChatRoomSerializer(chat_room).data, status=status.HTTP_200_OK)


class ChatMessageListCreate(APIView):
    """
    GET  /api/batches/<batch_id>/chat/messages/  — list messages
    POST /api/batches/<batch_id>/chat/messages/  — send a message
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_room_and_check(self, request, batch_id):
        batch = generics.get_object_or_404(Batch, batch_id=batch_id)
        chat_room = generics.get_object_or_404(BatchChatRoom, batch=batch)
        is_member = ChatMember.objects.filter(room=chat_room, customer=request.user).exists()
        is_staff = request.user.is_staff
        if not is_member and not is_staff:
            return None, Response({'detail': 'You are not a member of this chat.'}, status=status.HTTP_403_FORBIDDEN)
        return chat_room, None

    def get(self, request, batch_id):
        chat_room, err = self._get_room_and_check(request, batch_id)
        if err:
            return err
        messages = chat_room.messages.select_related('sender').all()
        return Response(ChatMessageSerializer(messages, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, batch_id):
        chat_room, err = self._get_room_and_check(request, batch_id)
        if err:
            return err
        content = request.data.get('content', '').strip()
        if not content:
            return Response({'content': 'Message content cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)
        message = ChatMessage.objects.create(room=chat_room, sender=request.user, content=content)
        return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Notification list + mark-read
# ---------------------------------------------------------------------------

class NotificationListView(APIView):
    """
    GET /api/notifications/   — list current user's notifications
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(recipient=request.user)
        return Response(NotificationSerializer(notifications, many=True).data, status=status.HTTP_200_OK)


class NotificationDetailView(APIView):
    """
    PATCH /api/notifications/<id>/   — mark as read
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, notif_id):
        notif = generics.get_object_or_404(Notification, id=notif_id, recipient=request.user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notif).data, status=status.HTTP_200_OK)
