# Backend Implementation Roadmap - Priority Order

**Frontend Status**: Ready to connect (HTTP layer complete)  
**Backend Status**: 40% complete (CRUD endpoints exist, auth/orders missing)  
**Target**: Full integration in 2-3 sprints

## Phase 1: AUTH ENDPOINTS (CRITICAL - Week 1)

**Blocking**: Everything else  
**Estimated Time**: 4-6 hours  
**Impact**: Allows frontend login/registration flow to work

### Tasks

1. **Create Auth Serializer** (batchit_app/serializers.py)
   ```python
   class AuthTokenSerializer(serializers.Serializer):
       email = serializers.EmailField()
       password = serializers.CharField(write_only=True)
       token = serializers.CharField(read_only=True)
       user = UserSerializer(read_only=True)
   
   class UserSerializer(serializers.ModelSerializer):
       class Meta:
           model = get_user_model()
           fields = ['id', 'email', 'first_name', 'last_name']
   ```

2. **Create Auth Views** (batchit_app/views.py)
   ```python
   class LoginView(APIView):
       authentication_classes = []
       permission_classes = [AllowAny]
       
       def post(self, request):
           email = request.data.get('email')
           password = request.data.get('password')
           user = authenticate(username=email, password=password)
           if user:
               token, created = Token.objects.get_or_create(user=user)
               return Response({
                   'token': token.key,
                   'user': UserSerializer(user).data
               })
           return Response({'detail': 'Invalid credentials'}, status=401)
   
   class LogoutView(APIView):
       permission_classes = [IsAuthenticated]
       
       def post(self, request):
           request.user.auth_token.delete()
           return Response({'detail': 'Successfully logged out'})
   
   class CurrentUserView(APIView):
       permission_classes = [IsAuthenticated]
       
       def get(self, request):
           return Response(UserSerializer(request.user).data)
   ```

3. **Register URL Routes** (batchit_app/urls.py)
   ```python
   path('api/auth/login/', LoginView.as_view(), name='login'),
   path('api/auth/logout/', LogoutView.as_view(), name='logout'),
   path('api/auth/me/', CurrentUserView.as_view(), name='current-user'),
   ```

4. **Test with Postman**
   - POST /api/auth/login/ with email/password
   - Verify token is returned
   - Use token in Authorization header for protected endpoints

### Frontend Impact
- ✅ LoginScreen will work
- ✅ AuthProvider will inject token
- ✅ Other services can now authenticate

---

## Phase 2: URL ROUTING BUG FIX (CRITICAL - Week 1)

**Blocking**: All detail endpoints  
**Estimated Time**: 1-2 hours  
**Impact**: Makes all PATCH/DELETE operations work

### Issue
URL patterns use `<pk>` but views use custom `lookup_field`:

```python
# BROKEN: urls.py
path('api/batches/<uuid:pk>/', BatchDetail.as_view()),

# BROKEN: views.py
class BatchDetail(generics.RetrieveUpdateDestroyAPIView):
    lookup_field = 'batch_id'  # Mismatch!
```

### Fix
Update [batchit_app/urls.py](batchit_app/urls.py):

```python
# FROM:
path('api/customers/<uuid:pk>/', CustomerDetail.as_view()),
path('api/providers/<uuid:pk>/', ProviderDetail.as_view()),
path('api/products/<uuid:pk>/', ProductDetail.as_view()),
path('api/batches/<uuid:pk>/', BatchDetail.as_view()),
path('api/batch-participants/<uuid:pk>/', BatchParticipantDetail.as_view()),
path('api/subscriptions/<uuid:pk>/', SubscriptionDetail.as_view()),

# TO:
path('api/customers/<uuid:customer_id>/', CustomerDetail.as_view()),
path('api/providers/<uuid:provider_id>/', ProviderDetail.as_view()),
path('api/products/<uuid:product_id>/', ProductDetail.as_view()),
path('api/batches/<uuid:batch_id>/', BatchDetail.as_view()),
path('api/batch-participants/<uuid:participant_id>/', BatchParticipantDetail.as_view()),
path('api/subscriptions/<uuid:subscription_id>/', SubscriptionDetail.as_view()),
```

### Verification
- `curl http://127.0.0.1:8000/api/batches/valid-uuid/` returns 200 (not 404)
- Update works: `PATCH /api/batches/valid-uuid/` with data

---

## Phase 3: ORDERS MODEL & ENDPOINTS (HIGH PRIORITY - Week 1-2)

**Blocking**: MyBatchesScreen, order history, order status tracking  
**Estimated Time**: 6-8 hours  
**Impact**: Allows users to see their order history and status

### Create Order Model (batchit_app/models.py)

Already partially exists as `BatchParticipant`. Consider renaming to `Order` or creating separate model:

```python
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('triggered', 'Triggered'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
    ]
    
    order_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    quantity_requested = models.FloatField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('customer', 'batch')
```

### Create Serializers (batchit_app/serializers.py)

```python
class OrderSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='batch.product.name')
    provider_name = serializers.CharField(source='batch.provider.business_name')
    batch_id = serializers.CharField(source='batch.batch_id')
    
    class Meta:
        model = Order
        fields = ['order_id', 'batch_id', 'customer', 'product_name', 
                  'quantity_requested', 'status', 'provider_name', 'created_at']
```

### Create Views (batchit_app/views.py)

```python
class OrderListCreate(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)

class OrderDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = OrderSerializer
    lookup_field = 'order_id'
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)
```

### Register URLs (batchit_app/urls.py)

```python
path('api/orders/', OrderListCreate.as_view(), name='order-list'),
path('api/orders/<uuid:order_id>/', OrderDetail.as_view(), name='order-detail'),
```

---

## Phase 4: JOIN BATCH ENDPOINT (HIGH PRIORITY - Week 2)

**Blocking**: JoinBatchScreen, batch participation flow  
**Estimated Time**: 2-3 hours  
**Impact**: Allows users to join batches

### Create Custom Action (batchit_app/views.py)

```python
from rest_framework.decorators import action
from rest_framework.response import Response

class BatchDetail(generics.RetrieveUpdateDestroyAPIView):
    # ... existing code ...
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def join(self, request, batch_id=None):
        batch = self.get_object()
        quantity = request.data.get('quantity_requested')
        
        order, created = Order.objects.get_or_create(
            batch=batch,
            customer=request.user,
            defaults={'quantity_requested': quantity, 'status': 'pending'}
        )
        
        if not created:
            order.quantity_requested = quantity
            order.save()
        
        return Response(
            OrderSerializer(order).data,
            status=201 if created else 200
        )
```

### Register URL
```python
# Automatic via ViewSet routing if using generics
# POST /api/batches/<uuid:batch_id>/join/
```

---

## Phase 5: NOTIFICATIONS MODEL & ENDPOINTS (MEDIUM PRIORITY - Week 3)

**Blocking**: NotificationsScreen, real-time notifications  
**Estimated Time**: 8-10 hours  
**Impact**: Users see batch updates, order status changes

### Notification Types
- Batch created (provider → followers)
- Batch filled (provider → participants)
- Order status changed (provider → customer)
- New provider (if followed)

### Suggested Approach
Use Django Signals to auto-create notifications on batch/order events:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Order)
def notify_on_order_status_change(sender, instance, created, **kwargs):
    if not created and instance.status_changed:
        Notification.objects.create(
            user=instance.customer,
            type='order_status_changed',
            message=f'Your order status: {instance.status}',
            related_order=instance
        )
```

---

## Phase 6: SEARCH ENDPOINTS (MEDIUM PRIORITY - Week 3)

**Blocking**: SearchScreen advanced filters  
**Estimated Time**: 4-6 hours  
**Impact**: Better batch discovery

### Add Query Parameters to Batch List

```python
class BatchListCreate(generics.ListCreateAPIView):
    def get_queryset(self):
        qs = Batch.objects.all()
        
        # Filters
        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)
        
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(product__category=category)
        
        # Location-based
        latitude = self.request.query_params.get('latitude')
        longitude = self.request.query_params.get('longitude')
        if latitude and longitude:
            # Use django-geojson or similar for distance calculation
            pass
        
        return qs
```

---

## Implementation Checklist

### Week 1 (Critical)
- [ ] Auth endpoints (login, logout, me, register)
- [ ] URL routing bug fix (6 detail endpoints)

### Week 2 (High Priority)
- [ ] Orders model and CRUD endpoints
- [ ] Join batch custom action
- [ ] Register with email/password validation
- [ ] Testing with Postman

### Week 3 (Medium Priority)
- [ ] Notifications model
- [ ] Search/filter endpoints
- [ ] Refresh token endpoint

### Testing & Deployment
- [ ] Integration tests for each endpoint
- [ ] Frontend + backend end-to-end testing
- [ ] Performance testing (pagination, filtering)
- [ ] Security review (CORS, auth, SQL injection)

---

## Frontend Verification

After each backend phase, frontend will automatically work:

| Phase | Frontend Feature Unblocked |
|-------|---------------------------|
| Auth Endpoints | Login, Register, Logout |
| URL Fix | Update, Delete any resource |
| Orders | MyBatchesScreen, order history |
| Join Endpoint | Join batch flow complete |
| Notifications | Notifications screen |
| Search | Search filters |

---

## Quick Start Command

```bash
cd ~/Desktop/BatchIt-Backend

# Run migrations
python manage.py migrate

# Create superuser (for admin panel)
python manage.py createsuperuser

# Start dev server
python manage.py runserver

# Test auth endpoint
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"pass123"}'
```

---

## References

- [FRONTEND_INTEGRATION_GUIDE.md](FRONTEND_INTEGRATION_GUIDE.md) - Full endpoint specifications
- Django REST Framework: https://www.django-rest-framework.org/
- Token Auth: https://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication
- Custom Actions: https://www.django-rest-framework.org/api-guide/viewsets/#marking-extra-actions-for-routing

---

**Frontend Team Status**: Ready and waiting ✅  
**Backend Team Status**: Implement Phase 1-2 for immediate results
