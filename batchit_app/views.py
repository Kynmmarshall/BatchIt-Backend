from rest_framework import generics, permissions
from .models import Customer, Provider, Product, Batch, BatchParticipant, Subscription
from .serializers import CustomerSerializer, ProviderSerializer, ProductSerializer, BatchSerializer, BatchParticipantSerializer, SubscriptionSerializer


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
