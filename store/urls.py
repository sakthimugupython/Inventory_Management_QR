from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True), name='root'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', views.logout_user, name='logout'),
    
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/update/', views.product_update, name='product_update'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    
    path('billing/', views.billing, name='billing'),
    path('api/get-product/', views.get_product, name='get_product'),
    path('api/save-sale/', views.save_sale, name='save_sale'),
    
    path('sales/', views.sales_list, name='sales_list'),
    path('invoice/<str:transaction_id>/', views.invoice, name='invoice'),
    
    path('reports/', views.reports, name='reports'),
    path('reports/data/', views.reports_data, name='reports_data'),
    path('reports/export/', views.reports_export, name='reports_export'),
    
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/update/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('api/categories/', views.categories_api, name='categories_api'),
]
