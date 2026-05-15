# Batchit API Endpoints Documentation

## Base URL
`http://127.0.0.1:8000/api/`

---

## 1. Customers
### List & Create
- **URL:** `/customers/`
- **Method:** `GET`, `POST`
- **Sample Data (POST):**
  ```json
  {
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "password": "securepassword123",
    "phone": "1234567890"
  }
  ```

---

## 2. Providers
### List & Create
- **URL:** `/providers/`
- **Method:** `GET`, `POST`
- **Sample Data (POST):**
  ```json
  {
    "business_name": "Bulk Essentials Inc.",
    "contact_email": "sales@bulkessentials.com",
    "category": "Grocery",
    "location": "New York, NY"
  }
  ```

---

## 3. Products
### List & Create
- **URL:** `/products/`
- **Method:** `GET`, `POST`
- **Sample Data (POST):**
  ```json
  {
    "provider": "UUID-FROM-PROVIDER",
    "name": "Toilet Rolls (20-pack)",
    "pack_size": 20,
    "pack_price": 20.00,
    "category": "Household"
  }
  ```

---

## 4. Batches
### List & Create
- **URL:** `/batches/`
- **Method:** `GET`, `POST`
- **Sample Data (POST):**
  ```json
  {
    "product": "UUID-FROM-PRODUCT",
    "provider": "UUID-FROM-PROVIDER",
    "total_quantity": 20,
    "notes": "Looking to split this pack!"
  }
  ```

---

## 5. Batch Participants
### Join a Batch
- **URL:** `/batch-participants/`
- **Method:** `POST`
- **Sample Data (POST):**
  ```json
  {
    "batch": "UUID-FROM-BATCH",
    "quantity_requested": 5
  }
  ```

---

## 6. Subscriptions
### Subscribe to a Provider
- **URL:** `/subscriptions/`
- **Method:** `POST`
- **Sample Data (POST):**
  ```json
  {
    "provider": "UUID-FROM-PROVIDER"
  }
  ```
