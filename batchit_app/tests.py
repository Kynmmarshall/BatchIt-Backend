from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from .models import Customer, Provider, Product, Batch

class BatchitAPITests(APITestCase):
    def setUp(self):
        self.customer = Customer.objects.create_user(username='testuser', email='test@test.com', password='password')
        self.provider = Provider.objects.create(business_name='Test Provider', contact_email='prov@test.com')
        self.product = Product.objects.create(provider=self.provider, name='Test Product', pack_size=10, pack_price=100.00)

    def test_create_batch(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse('batch-list-create')
        data = {
            'product': self.product.product_id,
            'provider': self.provider.provider_id,
            'total_quantity': 10,
            'notes': 'Test batch'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Batch.objects.count(), 1)

    def test_list_products(self):
        url = reverse('product-list-create')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)
