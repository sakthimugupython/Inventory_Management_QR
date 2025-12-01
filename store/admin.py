from django.contrib import admin
from .models import Category, Product, Sales, SalesItem

admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Sales)
admin.site.register(SalesItem)
