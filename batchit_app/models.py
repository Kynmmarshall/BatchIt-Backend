import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator
from django.conf import settings

# ─────────────────────────────────────────────
# CUSTOMER
# ─────────────────────────────────────────────

class CustomUserManager(BaseUserManager):

    def create_user(self, name, email, password, **extra_fields):
        if not name:
            raise ValueError("Name is required")
        if not email:
            raise ValueError("Email is required")
        if not password:
            raise ValueError("Password is required")

        email = self.normalize_email(email)

        user = self.model(
            name=name,
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.is_active = True
        user.save(using=self._db)

        return user

    def create_superuser(self, name, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(name, email, password, **extra_fields)
 
class CustomUser(AbstractBaseUser, PermissionsMixin):

    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    profile_photo_url = models.URLField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects = CustomUserManager()

    class Meta:
        db_table = "customers"
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return f"{self.name} <{self.email}>"

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

# ─────────────────────────────────────────────
# CUSTOMER
# ─────────────────────────────────────────────

class Customer(models.Model):

    customer_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile"
    )

    preferences = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.user.name} - Customer"

# ─────────────────────────────────────────────
# PROVIDER
# ─────────────────────────────────────────────

class Provider(models.Model):

    class Category(models.TextChoices):
        GROCERY = "grocery", "Grocery"
        ELECTRONICS = "electronics", "Electronics"
        HOUSEHOLD = "household", "Household"
        HEALTH = "health", "Health & Beauty"
        CLOTHING = "clothing", "Clothing"
        OTHER = "other", "Other"

    provider_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="provider_profile"
    )

    business_name = models.CharField(max_length=255)
    logo_url = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True)

    category = models.CharField(
        max_length=50,
        choices=Category.choices,
        default=Category.OTHER
    )

    location = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField()

    rating = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0)],
    )

    subscriber_count = models.PositiveIntegerField(default=0)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "providers"
        verbose_name = "Provider"
        verbose_name_plural = "Providers"
        ordering = ["-subscriber_count", "-rating"]

    def __str__(self):
        return self.business_name

# ─────────────────────────────────────────────
# PRODUCT
# ─────────────────────────────────────────────

class Product(models.Model):
    product_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="products",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True, null=True)
    # Total units in one bulk pack (e.g. 20 toilet rolls)
    pack_size = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    pack_price = models.DecimalField(max_digits=10, decimal_places=2)
    # Derived field: pack_price / pack_size — stored for query efficiency
    unit_price = models.DecimalField(max_digits=10, decimal_places=4, editable=False)
    category = models.CharField(max_length=100, blank=True)
    in_stock = models.BooleanField(default=True)

    class Meta:
        db_table = "products"
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def save(self, *args, **kwargs):
        if self.pack_size and self.pack_price:
            self.unit_price = self.pack_price / self.pack_size
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.provider.business_name})"


# ─────────────────────────────────────────────
# SUBSCRIPTION
# ─────────────────────────────────────────────

class Subscription(models.Model):
    subscription_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    # Granular notification preferences, e.g. {"all_batches": true, "categories": ["grocery"]}
    notification_prefs = models.JSONField(default=dict, blank=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscriptions"
        unique_together = [("customer", "provider")]
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    def __str__(self):
        return f"{self.customer.name} → {self.provider.business_name}"


# ─────────────────────────────────────────────
# BATCH
# ─────────────────────────────────────────────

class Batch(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        FILLED = "filled", "Filled"
        CONFIRMED = "confirmed", "Confirmed"
        FULFILLED = "fulfilled", "Fulfilled"
        EXPIRED = "expired", "Expired"

    batch_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="batches",
    )
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="batches",
    )
    creator = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="created_batches",
    )
    # Should equal the product's pack_size
    total_quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    # Sum of all BatchParticipant.quantity_requested — updated on join
    filled_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "batches"
        verbose_name = "Batch"
        verbose_name_plural = "Batches"
        indexes = [
            models.Index(fields=["status", "provider"]),
            models.Index(fields=["created_at"]),
        ]

    @property
    def remaining_quantity(self):
        return self.total_quantity - self.filled_quantity

    @property
    def is_full(self):
        return self.filled_quantity >= self.total_quantity

    def __str__(self):
        return f"Batch {self.batch_id} — {self.product.name} [{self.status}]"


# ─────────────────────────────────────────────
# BATCH PARTICIPANT
# ─────────────────────────────────────────────

class BatchParticipant(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        FULFILLED = "fulfilled", "Fulfilled"

    participant_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="batch_participations",
    )
    quantity_requested = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    joined_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    class Meta:
        db_table = "batch_participants"
        unique_together = [("batch", "customer")]
        verbose_name = "Batch Participant"
        verbose_name_plural = "Batch Participants"

    def __str__(self):
        return (
            f"{self.customer.name} in batch {self.batch.batch_id} "
            f"({self.quantity_requested} units)"
        )


# ─────────────────────────────────────────────
# NOTIFICATION
# ─────────────────────────────────────────────

class Notification(models.Model):
    class EventType(models.TextChoices):
        NEW_BATCH = "new_batch", "New Batch"
        BATCH_JOINED = "batch_joined", "Batch Joined"
        BATCH_FILLED = "batch_filled", "Batch Filled"
        ORDER_CONFIRMED = "order_confirmed", "Order Confirmed"
        ORDER_READY = "order_ready", "Order Ready"
        BATCH_EXPIRED = "batch_expired", "Batch Expired"
        NEW_PROVIDER_DEAL = "new_provider_deal", "New Provider Deal"
        PROFILE_REMINDER = "profile_reminder", "Profile Reminder"

    notification_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    summary = models.CharField(max_length=512)
    # Optional FK to the batch or provider this notification relates to
    related_batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    related_provider = models.ForeignKey(
        Provider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.event_type}] → {self.customer.name}"