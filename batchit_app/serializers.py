from rest_framework import serializers
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
