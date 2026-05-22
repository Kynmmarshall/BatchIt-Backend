# Frontend-Backend Integration Guide

**Status**: Frontend services updated to make real HTTP calls to Django backend

**Last Updated**: May 16, 2026

## Overview

The Flutter frontend has been updated to communicate with the Django REST Framework backend via real HTTP requests instead of mock data. This document outlines the backend API endpoints that must be implemented for full integration.

## Frontend Architecture Changes

### HTTP Client Setup
- **File**: [lib/services/api_client.dart](../lib/services/api_client.dart)
- **Purpose**: Singleton HTTP client that handles all requests, token management, and error handling
- **Features**:
  - Automatic token injection in `Authorization: Token <token>` header
  - Base URL: `http://127.0.0.1:8000/api`
  - Request timeout: 30 seconds
  - JSON serialization/deserialization
  - Meaningful error messages

### Updated Services

All service layers now make real HTTP calls with fallback to mock data on error (for development):

1. **[lib/services/auth_service.dart](../lib/services/auth_service.dart)**
   - `loginWithEmail()` → POST `/api/auth/login/`
   - `registerWithEmail()` → POST `/api/auth/register/`
   - `getCurrentUser()` → GET `/api/auth/me/`
   - `logout()` → POST `/api/auth/logout/`
   - `refreshToken()` → POST `/api/auth/refresh/`

2. **[lib/services/batch_service.dart](../lib/services/batch_service.dart)**
   - `fetchNearbyBatches()` → GET `/api/batches/?status=open`
   - `createBatch()` → POST `/api/batches/`
   - `fetchBatchById()` → GET `/api/batches/<id>/`
   - `updateBatch()` → PATCH `/api/batches/<id>/`
   - `joinBatch()` → POST `/api/batches/<id>/join/`
   - `deleteBatch()` → DELETE `/api/batches/<id>/`

3. **[lib/services/order_service.dart](../lib/services/order_service.dart)**
   - `fetchOrders()` → GET `/api/orders/?status=<status>`
   - `createOrder()` → POST `/api/orders/`
   - `fetchOrderById()` → GET `/api/orders/<id>/`
   - `updateOrderStatus()` → PATCH `/api/orders/<id>/`
   - `deleteOrder()` → DELETE `/api/orders/<id>/`

### Provider Updates

**[lib/providers/auth_provider.dart](../lib/providers/auth_provider.dart)**
- Injects auth token into ApiClient after successful login
- Calls backend logout endpoint during user logout
- Enhanced error handling with fallback to null user state

## Backend Implementation Checklist

### 1. Authentication Endpoints (CRITICAL - blocks all other endpoints)

**POST /api/auth/login/**
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword"
  }
  ```
- **Response** (200):
  ```json
  {
    "token": "abc123token...",
    "user": {
      "id": "user-uuid",
      "email": "user@example.com",
      "first_name": "John",
      "last_name": "Doe"
    }
  }
  ```
- **Error Response** (401):
  ```json
  {
    "detail": "Invalid email or password"
  }
  ```

**POST /api/auth/register/**
- **Request Body**:
  ```json
  {
    "email": "newuser@example.com",
    "password": "securepassword",
    "first_name": "Jane",
    "last_name": "Smith"
  }
  ```
- **Response** (201): Same as login response
- **Error Response** (400):
  ```json
  {
    "email": ["This email is already registered."],
    "password": ["Password too short."]
  }
  ```

**GET /api/auth/me/**
- **Headers**: `Authorization: Token <token>`
- **Response** (200):
  ```json
  {
    "id": "user-uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
  ```
- **Error Response** (401): `{"detail": "Invalid token"}`

**POST /api/auth/logout/**
- **Headers**: `Authorization: Token <token>`
- **Request Body**: `{}`
- **Response** (200): `{"detail": "Successfully logged out"}`

**POST /api/auth/refresh/**
- **Headers**: `Authorization: Token <token>`
- **Request Body**: `{}`
- **Response** (200):
  ```json
  {
    "token": "new-token-string"
  }
  ```

### 2. Batch Endpoints

**GET /api/batches/**
- **Query Parameters** (optional):
  - `status`: "open", "filled", "confirmed", "fulfilled", "expired"
  - `latitude`, `longitude`, `radius_km`: for location-based filtering
  - `page`, `page_size`: pagination
- **Response** (200):
  ```json
  {
    "count": 42,
    "next": "http://...",
    "previous": null,
    "results": [
      {
        "batch_id": "batch-uuid",
        "product_name": "Potatoes",
        "total_quantity": 50,
        "filled_quantity": 30,
        "status": "open",
        "location": "Hay Salam",
        "provider_name": "Hub Ain Sebaa",
        "expires_at": "2026-05-23T00:00:00Z",
        "created_at": "2026-05-16T10:00:00Z"
      }
    ]
  }
  ```

**POST /api/batches/**
- **Headers**: `Authorization: Token <token>`
- **Request Body**:
  ```json
  {
    "product_name": "Potatoes",
    "total_quantity": 50,
    "location": "Hay Salam",
    "notes": "Premium quality potatoes",
    "expires_at": "2026-05-23T00:00:00Z",
    "status": "open"
  }
  ```
- **Response** (201): Same as batch list item

**GET /api/batches/<id>/**
- **Response** (200): Single batch object

**PATCH /api/batches/<id>/**
- **Headers**: `Authorization: Token <token>`
- **Request Body** (any fields):
  ```json
  {
    "status": "fulfilled",
    "filled_quantity": 50,
    "notes": "Updated notes"
  }
  ```
- **Response** (200): Updated batch object

**POST /api/batches/<id>/join/**
- **Headers**: `Authorization: Token <token>`
- **Request Body**:
  ```json
  {
    "quantity_requested": 5
  }
  ```
- **Response** (201):
  ```json
  {
    "participant_id": "participant-uuid",
    "batch_id": "batch-uuid",
    "customer_id": "user-uuid",
    "quantity_requested": 5,
    "status": "pending",
    "joined_at": "2026-05-16T10:00:00Z"
  }
  ```

**DELETE /api/batches/<id>/**
- **Headers**: `Authorization: Token <token>`
- **Response** (204): No content

### 3. Orders Endpoints (TODO: Not yet in backend)

**GET /api/orders/**
- **Query Parameters** (optional):
  - `status`: "pending", "triggered", "delivered", "completed"
  - `page`, `page_size`: pagination
- **Response** (200):
  ```json
  {
    "count": 10,
    "next": null,
    "previous": null,
    "results": [
      {
        "order_id": "order-uuid",
        "batch_id": "batch-uuid",
        "product_name": "Potatoes",
        "quantity_requested": 5,
        "status": "pending",
        "provider_name": "Hub Ain Sebaa",
        "created_at": "2026-05-16T10:00:00Z"
      }
    ]
  }
  ```

**POST /api/orders/**
- **Headers**: `Authorization: Token <token>`
- **Request Body**:
  ```json
  {
    "batch_id": "batch-uuid",
    "quantity_requested": 5
  }
  ```
- **Response** (201): Order object

**GET /api/orders/<id>/**
- **Response** (200): Single order object

**PATCH /api/orders/<id>/**
- **Headers**: `Authorization: Token <token>`
- **Request Body**:
  ```json
  {
    "status": "delivered"
  }
  ```
- **Response** (200): Updated order object

**DELETE /api/orders/<id>/**
- **Headers**: `Authorization: Token <token>`
- **Response** (204): No content

## Known Issues to Fix on Backend

### 1. URL Routing Bug (CRITICAL)
All detail endpoints have a mismatch between URL kwarg and lookup_field:

**Current (BROKEN)**:
```python
url(r'^api/batches/(?P<pk>[^/.]+)/$', BatchDetail.as_view()),
# But view uses: lookup_field = 'batch_id'
```

**Fix Required**:
```python
url(r'^api/batches/(?P<batch_id>[^/.]+)/$', BatchDetail.as_view()),
```

**Affected Endpoints**:
- `/api/customers/<pk>` (should be `<customer_id>`)
- `/api/providers/<pk>` (should be `<provider_id>`)
- `/api/products/<pk>` (should be `<product_id>`)
- `/api/batches/<pk>` (should be `<batch_id>`)
- `/api/batch-participants/<pk>` (should be `<participant_id>`)
- `/api/subscriptions/<pk>` (should be `<subscription_id>`)

### 2. Missing Auth Model (TODO)
Currently using Django's built-in User model. Consider:
- Extending with customer_id (UUID)
- Adding phone field
- Adding profile_photo_url field
- Creating Customer model that extends User (if not already done)

### 3. Missing Endpoints
- Auth endpoints: /api/auth/login/, /api/auth/register/, /api/auth/me/, /api/auth/logout/, /api/auth/refresh/
- Orders endpoints: Full CRUD for /api/orders/
- Notifications endpoints: Full CRUD for /api/notifications/
- Search endpoints: Enhanced search for /api/batches/search/, /api/providers/search/
- Profile endpoints: /api/profile/, /api/profile/settings/
- Join action: POST /api/batches/<id>/join/ (custom action)

## Frontend Field Mapping

Frontend services map backend fields to UI models:

### Batch Mapping
| Backend Field | Frontend Field | Notes |
|---|---|---|
| `batch_id` / `id` | `id` | UUID primary key |
| `product_name` | `productName` | Batch product |
| `total_quantity` | `bulkSizeKg` | Target batch size |
| `filled_quantity` | `currentQuantityKg` | Current participation |
| `location` | `locationName` | Delivery location |
| `provider_name` / `provider` | `hubName` | Provider/hub name |

### Order Mapping
| Backend Field | Frontend Field | Notes |
|---|---|---|
| `order_id` / `id` | `id` | UUID primary key |
| `product_name` | `productName` | Order product |
| `quantity_requested` | `quantityKg` | Quantity ordered |
| `status` | `status` | Order status enum |
| `provider_name` / `provider` | `hubName` | Provider/hub name |
| `batch_id` | `batchId` | Link to parent batch |

## Testing the Integration

### Prerequisites
1. Backend running on `http://127.0.0.1:8000`
2. All auth endpoints implemented
3. Token authentication configured in Django

### Manual Testing Flow
1. **Login Screen**:
   - Enter email/password
   - Frontend calls POST `/api/auth/login/`
   - Backend returns token
   - Token injected into ApiClient
   - Navigate to Home screen

2. **Home Screen**:
   - Frontend calls GET `/api/batches/?status=open`
   - Backend returns list of batches
   - Display in FlatList

3. **Create Batch**:
   - Fill form with product name, bulk size, location
   - Frontend calls POST `/api/batches/`
   - Backend creates batch with creator=current user

4. **Join Batch**:
   - Select quantity
   - Frontend calls POST `/api/batches/<id>/join/`
   - Backend creates BatchParticipant entry

### Debugging
- Check browser DevTools Network tab to view HTTP requests/responses
- Enable request/response logging in ApiClient (add print statements)
- Use Django admin to verify database records

## Next Steps

1. **Immediate** (blocking frontend):
   - Fix URL routing bug for all detail endpoints
   - Implement auth endpoints (/api/auth/*)
   - Verify token authentication works

2. **Short-term**:
   - Implement orders endpoints
   - Add custom /batches/<id>/join/ action endpoint
   - Implement notifications model/endpoints

3. **Medium-term**:
   - Add search endpoints with filtering
   - Add profile/settings endpoints
   - Implement location-based batch filtering

4. **Testing**:
   - Integration tests for auth flow
   - End-to-end tests for batch creation and joining
   - Performance testing for list endpoints

## References

- Frontend Services: `lib/services/`
- Frontend Models: `lib/models/`
- Django REST Framework Docs: https://www.django-rest-framework.org/
- Token Authentication: https://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication
