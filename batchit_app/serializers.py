from rest_framework import serializers
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from .models import Customer, Provider, Product, Batch, BatchParticipant, Subscription

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
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        # Authenticate using email as username (Customer uses email as USERNAME_FIELD)
        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")

        data['user'] = user
        return data


class RegisterSerializer(serializers.Serializer):
    """
    Serializer for user registration.
    Creates a new Customer and returns token.
    """
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)

    def validate(self, data):
        if Customer.objects.filter(email=data.get('email')).exists():
            raise serializers.ValidationError("Email already registered.")
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
        read_only_fields = '__all__'
