from rest_framework import serializers
from .models import *

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

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ('product_id', 'created_at', 'updated_at')



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
        )

        read_only_fields = (
            'product_id',
            'unit_price',
        )