from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Customer, Provider, Product, Batch, BatchParticipant, Subscription

@admin.register(Customer)
class CustomerAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'category', 'contact_email', 'verified', 'created_at')
    search_fields = ('business_name', 'category')
    list_filter = ('verified', 'category')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'pack_size', 'pack_price', 'unit_price', 'in_stock')
    search_fields = ('name', 'provider__business_name')
    list_filter = ('in_stock', 'category')

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('batch_id', 'product', 'provider', 'creator', 'status', 'filled_quantity', 'total_quantity')
    list_filter = ('status', 'provider')
    search_fields = ('product__name', 'provider__business_name', 'creator__email')

@admin.register(BatchParticipant)
class BatchParticipantAdmin(admin.ModelAdmin):
    list_display = ('batch', 'customer', 'quantity_requested', 'status')
    list_filter = ('status',)
    search_fields = ('customer__email', 'batch__batch_id')

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'provider', 'subscribed_at')
    search_fields = ('customer__email', 'provider__business_name')
