from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
import secrets
import string


class Customer(AbstractUser):
    """
    Represents an individual user who wants to purchase a portion of a bulk product.
    Inherits from Django's AbstractUser for authentication and basic fields.
    """
    customer_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    profile_photo_url = models.URLField(blank=True, null=True)
    preferences = models.JSONField(blank=True, null=True, default=dict) # e.g., product categories, budget range, region
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name'] # Add other required fields if necessary

    def __str__(self):
        return self.email

class Provider(models.Model):
    """
    Represents a business, retailer, or wholesaler that lists products and fulfills orders.
    """
    provider_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    logo_url = models.URLField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True) # e.g., Grocery, Electronics, Household
    location = models.CharField(max_length=255, blank=True, null=True)
    contact_email = models.EmailField()
    rating = models.FloatField(blank=True, null=True) # Average rating (float)
    subscriber_count = models.IntegerField(default=0)
    verified = models.BooleanField(default=False)
    owner_name = models.CharField(max_length=255, blank=True, default='')
    owner_email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    address = models.CharField(max_length=500, blank=True, default='')
    registration_number = models.CharField(max_length=100, blank=True, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('verified', 'Verified'), ('rejected', 'Rejected')],
        default='pending',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_verified(self):
        return self.status == 'verified'

    def __str__(self):
        return self.business_name

class Product(models.Model):
    """
    Represents a product listed by a provider.
    """
    product_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    pack_size = models.PositiveIntegerField() # Total units per bulk pack
    pack_price = models.DecimalField(max_digits=10, decimal_places=2) # Full pack price
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False) # Calculated: pack_price / pack_size
    category = models.CharField(max_length=100, blank=True, null=True)
    in_stock = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Calculate unit_price if pack_size is not zero
        if self.pack_size > 0:
            self.unit_price = self.pack_price / self.pack_size
        else:
            self.unit_price = self.pack_price # Or handle as an error, depending on requirements
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.provider.business_name})"

class Batch(models.Model):
    """
    Represents a group purchase request.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('filled', 'Filled'),
        ('confirmed', 'Confirmed'),
        ('fulfilled', 'Fulfilled'),
        ('expired', 'Expired'),
    ]
    batch_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='batches')
    provider = models.ForeignKey(Provider, on_delete=models.SET_NULL, null=True, blank=True, related_name='batches')
    creator = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='created_batches')
    product_name = models.CharField(max_length=255, blank=True, default='')
    total_quantity = models.FloatField(default=0)
    filled_quantity = models.FloatField(default=0)
    location_name = models.CharField(max_length=255, blank=True, default='')
    image_url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    expires_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Batch for {self.product.name} ({self.status})"

class BatchParticipant(models.Model):
    """
    Represents a customer participating in a batch.
    """
    participant_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='participants')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='participating_batches')
    quantity_requested = models.PositiveIntegerField() # How many units this customer wants
    joined_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('fulfilled', 'Fulfilled'),
    ], default='pending')

    def __str__(self):
        return f"{self.customer.email} in batch {self.batch.batch_id}"

# Subscription Model (as suggested by the document for explicit management)
class Subscription(models.Model):
    """
    Manages the relationship between a Customer and a Provider.
    """
    subscription_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='subscriptions')
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='subscribers')
    subscribed_at = models.DateTimeField(auto_now_add=True)
    # Notification preferences could be added here if they become more complex than a simple JSON in Customer.preferences

    class Meta:
        unique_together = ('customer', 'provider') # A customer can only subscribe to a provider once

    def __str__(self):
        return f"Subscription of {self.customer.email} to {self.provider.business_name}"


class EmailVerificationCode(models.Model):
    """
    Stores temporary email verification codes sent to users for registration/email verification.
    Codes expire after a set duration (default: 15 minutes).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6, db_index=True)  # 6-digit code
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # Code expires 15 min after creation

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=15)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if code has not expired and not been used."""
        return not self.is_used and timezone.now() < self.expires_at

    @staticmethod
    def generate_code():
        """Generate a random 6-digit verification code."""
        return ''.join(secrets.choice(string.digits) for _ in range(6))

    def __str__(self):
        return f"Verification code for {self.email}"
