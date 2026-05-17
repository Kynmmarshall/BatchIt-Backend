from rest_framework import serializers
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from .models import Customer, Provider, Product, Batch, BatchParticipant, Subscription, EmailVerificationCode
import re

# Existing BatchSerializer
class BatchSerializer(serializers.ModelSerializer):
    remaining_quantity = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()

    class Meta:
        model = Batch
        fields = (
            'batch_id',
            'product',
            'provider',
            'creator',
            'total_quantity',
            'filled_quantity',
            'remaining_quantity',
            'is_full',
            'status',
            'expires_at',
            'created_at',
            'notes',
        )
        read_only_fields = (
            'batch_id',
            'filled_quantity',
            'status',
            'created_at',
            'remaining_quantity',
            'is_full',
        )

# Existing ProductSerializer (The file had a duplicate ProductSerializer, I'm consolidating and keeping the more comprehensive one)
class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            'product_id',
            'provider',
            'name',
            'description',
            'image_url',
            'pack_size',
            'pack_price',
            'unit_price',
            'category',
            'in_stock',
            'created_at', # Added created_at as it's in the model
        )
        read_only_fields = (
            'product_id',
            'unit_price',
            'created_at',
        )

# New Serializers

class CustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for the Customer model.
    Note: Inherits from AbstractUser, so password and other sensitive fields are handled by Django's auth system.
    We will expose email as username.
    """
    class Meta:
        model = Customer
        fields = (
            'customer_id',
            'email', # Using email as username
            'first_name',
            'last_name',
            'phone',
            'profile_photo_url',
            'preferences',
            'created_at',
            'last_login',
        )
        read_only_fields = (
            'customer_id',
            'email',
            'created_at',
            'last_login',
        )
        # For registration, you'd typically use a different serializer that includes password.
        # For updates, 'email' might be non-editable if it's the username.

class ProviderSerializer(serializers.ModelSerializer):
    """
    Serializer for the Provider model.
    """
    class Meta:
        model = Provider
        fields = '__all__'
        read_only_fields = ('provider_id', 'subscriber_count', 'verified', 'created_at')

class BatchParticipantSerializer(serializers.ModelSerializer):
    """
    Serializer for the BatchParticipant model.
    """
    class Meta:
        model = BatchParticipant
        fields = '__all__'
        read_only_fields = ('participant_id', 'joined_at', 'status') # Status might be updated by system


class OrderSerializer(serializers.ModelSerializer):
    """
    Frontend-facing order serializer backed by BatchParticipant.
    """
    order_id = serializers.UUIDField(source='participant_id', read_only=True)
    batch_id = serializers.UUIDField(source='batch.batch_id', read_only=True)
    product_name = serializers.CharField(source='batch.product.name', read_only=True)
    provider_name = serializers.CharField(source='batch.provider.business_name', read_only=True)

    class Meta:
        model = BatchParticipant
        fields = (
            'order_id',
            'batch_id',
            'product_name',
            'provider_name',
            'quantity_requested',
            'status',
            'joined_at',
        )
        read_only_fields = (
            'order_id',
            'batch_id',
            'product_name',
            'provider_name',
            'joined_at',
        )


class OrderCreateSerializer(serializers.Serializer):
    """
    Input serializer for creating an order (joining a batch).
    """
    batch_id = serializers.UUIDField()
    quantity_requested = serializers.IntegerField(min_value=1)


class OrderStatusUpdateSerializer(serializers.Serializer):
    """
    Input serializer for updating order status.
    """
    status = serializers.ChoiceField(choices=BatchParticipant._meta.get_field('status').choices)


class JoinBatchSerializer(serializers.Serializer):
    """
    Input serializer for /batches/<id>/join/ endpoint.
    """
    quantity_requested = serializers.IntegerField(min_value=1)

class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for the Subscription model.
    """
    class Meta:
        model = Subscription
        fields = '__all__'
        read_only_fields = ('subscription_id', 'subscribed_at')


# --- Auth Serializers ---

class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    Accepts email and password, returns token and user info.
    """
    email = serializers.EmailField(error_messages={
        'invalid': 'Please enter a valid email address.',
        'required': 'Email is required.',
        'blank': 'Email cannot be blank.',
    })
    password = serializers.CharField(
        write_only=True,
        error_messages={
            'required': 'Password is required.',
            'blank': 'Password cannot be blank.',
        }
    )

    def validate_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Email cannot be empty.')
        # Prevent local-part starting with invalid characters like '-'
        if not re.match(r'^[A-Za-z0-9][A-Za-z0-9._%+\-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', value):
            raise serializers.ValidationError('Please enter a valid email address.')
        return value

    def validate_password(self, value):
        if not value or len(value) < 1:
            raise serializers.ValidationError('Password is required.')
        return value

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            raise serializers.ValidationError('Email and password are required.')

        # Check if account exists first
        try:
            customer = Customer.objects.get(email=email)
        except Customer.DoesNotExist:
            raise serializers.ValidationError({'email': 'No account found with this email address.'})

        # Authenticate using email as username (Customer uses email as USERNAME_FIELD)
        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError({'password': 'Incorrect password. Please try again.'})

        data['user'] = user
        return data


class RegisterSerializer(serializers.Serializer):
    """
    Serializer for user registration.
    Creates a new Customer and returns token.
    """
    email = serializers.EmailField(error_messages={
        'invalid': 'Please enter a valid email address.',
        'required': 'Email is required.',
        'blank': 'Email cannot be blank.',
    })
    username = serializers.CharField(
        max_length=150,
        error_messages={
            'required': 'Username is required.',
            'blank': 'Username cannot be blank.',
            'max_length': 'Username cannot exceed 150 characters.',
        }
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            'required': 'Password is required.',
            'blank': 'Password cannot be blank.',
            'min_length': 'Password must be at least 8 characters long.',
        }
    )
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Email cannot be empty.')
        if not re.match(r'^[A-Za-z0-9][A-Za-z0-9._%+\-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', value):
            raise serializers.ValidationError('Please enter a valid email address.')
        if Customer.objects.filter(email=value).exists():
            raise serializers.ValidationError('This email is already registered. Please try logging in.')
        return value

    def validate_username(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Username cannot be empty.')
        if Customer.objects.filter(username=value).exists():
            raise serializers.ValidationError('This username is already taken. Please choose another.')
        return value

    def validate_password(self, value):
        if not value or len(value) < 8:
            raise serializers.ValidationError('Password must be at least 8 characters long.')
        if value.isdigit():
            raise serializers.ValidationError('Password cannot be only numbers.')
        return value

    def validate(self, data):
        email = data.get('email')
        if Customer.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'This email is already registered.'})
        return data

    def create(self, validated_data):
        # Create customer with email, username, and password
        user = Customer.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        return user


class AuthDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed customer/user info (used in login/register/me responses).
    """
    class Meta:
        model = Customer
        fields = (
            'customer_id',
            'email',
            'username',
            'first_name',
            'last_name',
            'phone',
            'profile_photo_url',
            'created_at',
        )
        read_only_fields = (
            'customer_id',
            'email',
            'username',
            'first_name',
            'last_name',
            'phone',
            'profile_photo_url',
            'created_at',
        )


class SendVerificationCodeSerializer(serializers.Serializer):
    """
    Serializer for requesting an email verification code.
    """
    email = serializers.EmailField(error_messages={
        'invalid': 'Please enter a valid email address.',
        'required': 'Email is required.',
        'blank': 'Email cannot be blank.',
    })
    # Rely on DRF's EmailField validation to avoid over-restrictive custom regexes.


class VerifyEmailCodeSerializer(serializers.Serializer):
    """
    Serializer for verifying an email code.
    Used during registration to verify email before creating account.
    """
    email = serializers.EmailField(error_messages={
        'invalid': 'Please enter a valid email address.',
        'required': 'Email is required.',
    })
    code = serializers.CharField(
        max_length=6,
        min_length=6,
        error_messages={
            'required': 'Verification code is required.',
            'max_length': 'Verification code must be 6 digits.',
            'min_length': 'Verification code must be 6 digits.',
        }
    )


class RegisterWithVerificationSerializer(serializers.Serializer):
    """
    Serializer for registration with email verification.
    Verifies the email code, then creates the user account.
    """
    email = serializers.EmailField(error_messages={
        'invalid': 'Please enter a valid email address.',
        'required': 'Email is required.',
    })
    code = serializers.CharField(
        max_length=6,
        min_length=6,
        error_messages={
            'required': 'Verification code is required.',
            'max_length': 'Verification code must be 6 digits.',
            'min_length': 'Verification code must be 6 digits.',
        }
    )
    username = serializers.CharField(
        max_length=150,
        error_messages={
            'required': 'Username is required.',
            'max_length': 'Username cannot exceed 150 characters.',
        }
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            'required': 'Password is required.',
            'min_length': 'Password must be at least 8 characters long.',
        }
    )
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('Verification code must contain only digits.')
        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError('Password must be at least 8 characters long.')
        if value.isdigit():
            raise serializers.ValidationError('Password cannot be only numbers.')
        return value

    def validate_username(self, value):
        if Customer.objects.filter(username=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate(self, data):
        email = data.get('email')
        code = data.get('code')

        # Verify email code is valid
        try:
            verification = EmailVerificationCode.objects.get(email=email, code=code)
            if not verification.is_valid():
                raise serializers.ValidationError({'code': 'Verification code has expired. Please request a new one.'})
        except EmailVerificationCode.DoesNotExist:
            raise serializers.ValidationError({'code': 'Invalid verification code. Please check and try again.'})

        # Check email not already registered
        if Customer.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'This email is already registered.'})

        return data

    def create(self, validated_data):
        # Mark verification code as used
        verification = EmailVerificationCode.objects.get(
            email=validated_data['email'],
            code=validated_data['code']
        )
        verification.is_used = True
        verification.save()

        # Create customer
        user = Customer.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        return user
