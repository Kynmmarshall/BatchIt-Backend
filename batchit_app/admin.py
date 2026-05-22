from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html, format_html_join
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
    readonly_fields = ('documents_download_links',)
    fields = (
        'business_name',
        'description',
        'logo_url',
        'category',
        'location',
        'contact_email',
        'owner_name',
        'owner_email',
        'phone',
        'address',
        'registration_number',
        'status',
        'rejection_message',
        'document_paths',
        'documents_download_links',
        'created_at',
    )

    def documents_download_links(self, obj):
        if not obj or not obj.document_paths:
            return 'No documents uploaded'
        links = []
        for idx, rel_path in enumerate(obj.document_paths):
            url = reverse('provider-document-download', kwargs={'provider_id': obj.provider_id, 'index': idx})
            file_name = rel_path.split('/')[-1]
            links.append((url, file_name))
        return format_html_join(
            '<br>',
            '<a href="{}" target="_blank" rel="noopener noreferrer">Download {}</a>',
            links,
        )

    documents_download_links.short_description = 'Provider documents'

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
