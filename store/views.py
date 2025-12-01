from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, F
from .models import Product, Category, Sales, SalesItem
from django.db import IntegrityError
from django.utils import timezone
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
import json
import datetime
from django.contrib import messages
from django.core.paginator import Paginator

from django.contrib.auth import logout

@login_required
def dashboard(request):
    total_products = Product.objects.count()
    today = timezone.now().date()
    sales_today = Sales.objects.filter(date_added__date=today).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    low_stock = Product.objects.filter(stock_quantity__lt=10).count()
    
    recent_sales = Sales.objects.order_by('-date_added')[:5]
    
    context = {
        'total_products': total_products,
        'sales_today': sales_today,
        'low_stock': low_stock,
        'recent_sales': recent_sales
    }
    return render(request, 'dashboard.html', context)

@login_required
def product_list(request):
    products = Product.objects.all().order_by('-id')
    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # build a compact page number window for navigation
    current = page_obj.number
    total = paginator.num_pages
    window = 3
    start = max(1, current - window)
    end = min(total, current + window)
    page_numbers = range(start, end + 1)

    context = {
        'page_obj': page_obj,
        'page_numbers': page_numbers,
        'total_pages': total,
    }
    return render(request, 'store/product_list.html', context)

@login_required
def product_create(request):
    if request.method == 'POST':
        barcode = request.POST.get('barcode')
        name = request.POST.get('name')
        price = request.POST.get('price')
        cost = request.POST.get('cost')
        stock = request.POST.get('stock')
        gst = request.POST.get('gst')
        category_val = request.POST.get('category')
        category = None
        # category may be passed as id (from select) or name (legacy). handle both.
        if category_val:
            try:
                # try id first
                category = Category.objects.get(pk=int(category_val))
            except Exception:
                category, created = Category.objects.get_or_create(name=category_val)

        # server-side uniqueness check to avoid IntegrityError from DB
        if Product.objects.filter(barcode=barcode).exists():
            messages.error(request, 'A product with this barcode already exists.')
            # re-render form with entered values so user can correct
            context = {
                'product': {
                    'barcode': barcode,
                    'name': name,
                    'price': price,
                    'cost': cost,
                    'stock_quantity': stock,
                    'gst_percentage': gst,
                        'category': category
                }
            }
            return render(request, 'store/product_form.html', context)

        try:
            Product.objects.create(
                barcode=barcode,
                name=name,
                price=price,
                cost=cost,
                stock_quantity=stock,
                gst_percentage=gst,
                category=category
            )
        except IntegrityError as e:
            # catch any unexpected unique constraint violations
            messages.error(request, 'Unable to add product: barcode must be unique.')
            context = {'product': {'barcode': barcode, 'name': name, 'price': price, 'cost': cost, 'stock_quantity': stock, 'gst_percentage': gst, 'category': category}}
            return render(request, 'store/product_form.html', context)
        messages.success(request, 'Product added successfully')
        return redirect('product_list')
    categories = Category.objects.all().order_by('name')
    return render(request, 'store/product_form.html', {'categories': categories})

@login_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        new_barcode = request.POST.get('barcode')
        # ensure barcode update won't conflict with an existing product
        if Product.objects.exclude(pk=product.pk).filter(barcode=new_barcode).exists():
            messages.error(request, 'Another product with this barcode already exists.')
            return render(request, 'store/product_form.html', {'product': product})

        product.barcode = new_barcode
        product.name = request.POST.get('name')
        product.price = request.POST.get('price')
        product.cost = request.POST.get('cost')
        product.stock_quantity = request.POST.get('stock')
        product.gst_percentage = request.POST.get('gst')
        category_val = request.POST.get('category')
        if category_val:
            try:
                category = Category.objects.get(pk=int(category_val))
            except Exception:
                category, created = Category.objects.get_or_create(name=category_val)
            product.category = category
        product.save()
        messages.success(request, 'Product updated successfully')
        return redirect('product_list')
    categories = Category.objects.all().order_by('name')
    return render(request, 'store/product_form.html', {'product': product, 'categories': categories})

@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted successfully')
        return redirect('product_list')
    return render(request, 'store/product_confirm_delete.html', {'product': product})

@login_required
def billing(request):
    return render(request, 'store/billing.html')

@login_required
def get_product(request):
    barcode = request.GET.get('barcode')
    try:
        product = Product.objects.get(barcode=barcode)
        return JsonResponse({
            'success': True,
            'barcode': product.barcode,
            'id': product.id,
            'name': product.name,
            'price': float(product.price),
            'stock': product.stock_quantity,
            'gst': float(product.gst_percentage)
        })
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product not found'})

@login_required
def save_sale(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = data.get('items')
            customer_name = data.get('customer_name')
            
            if not items:
                return JsonResponse({'success': False, 'error': 'No items in cart'})
                
            transaction_id = f"TRX-{int(timezone.now().timestamp())}"
            sale = Sales.objects.create(
                transaction_id=transaction_id,
                customer_name=customer_name,
                user=request.user,
                total_amount=0
            )
            
            total_amount = 0
            
            for item in items:
                product_id = item.get('id')
                quantity = int(item.get('quantity'))
                
                product = Product.objects.get(id=product_id)
                
                if product.stock_quantity < quantity:
                    sale.delete()
                    return JsonResponse({'success': False, 'error': f'Not enough stock for {product.name}'})
                
                product.stock_quantity -= quantity
                product.save()
                
                SalesItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    price=product.price,
                    total=product.price * quantity
                )
                
                total_amount += (float(product.price) * quantity)
                
            sale.total_amount = total_amount
            sale.save()
            
            return JsonResponse({'success': True, 'transaction_id': transaction_id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def sales_list(request):
    qs = Sales.objects.all().order_by('-date_added')
    # filters from query params
    start = request.GET.get('start_date')
    end = request.GET.get('end_date')
    category_id = request.GET.get('category')
    search_txn = request.GET.get('search_txn', '').strip()
    if search_txn:
        qs = qs.filter(transaction_id__icontains=search_txn)
    if start:
        try:
            start_dt = datetime.datetime.strptime(start, '%Y-%m-%d')
            qs = qs.filter(date_added__date__gte=start_dt.date())
        except Exception:
            pass
    if end:
        try:
            end_dt = datetime.datetime.strptime(end, '%Y-%m-%d')
            qs = qs.filter(date_added__date__lte=end_dt.date())
        except Exception:
            pass
    if category_id:
        try:
            cid = int(category_id)
            qs = qs.filter(items__product__category__id=cid).distinct()
            selected_category = cid
        except Exception:
            selected_category = None
    else:
        selected_category = None

    categories = Category.objects.all().order_by('name')
    return render(request, 'store/sales_list.html', {'sales': qs, 'categories': categories, 'selected_category': selected_category, 'start_date': start, 'end_date': end, 'search_txn': search_txn})


@login_required
def category_list(request):
    categories = Category.objects.all().order_by('name')
    return render(request, 'store/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return render(request, 'store/category_form.html')
        if Category.objects.filter(name=name).exists():
            messages.error(request, 'Category with this name already exists.')
            return render(request, 'store/category_form.html', {'name': name})
        Category.objects.create(name=name)
        messages.success(request, 'Category created successfully.')
        return redirect('category_list')
    return render(request, 'store/category_form.html')


@login_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return render(request, 'store/category_form.html', {'category': category})
        if Category.objects.exclude(pk=pk).filter(name=name).exists():
            messages.error(request, 'Category with this name already exists.')
            return render(request, 'store/category_form.html', {'category': category})
        category.name = name
        category.save()
        messages.success(request, 'Category updated successfully.')
        return redirect('category_list')
    return render(request, 'store/category_form.html', {'category': category})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted successfully.')
        return redirect('category_list')
    return render(request, 'store/category_confirm_delete.html', {'category': category})


@login_required
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('name') or request.body and json.loads(request.body).get('name')
        if not name:
            return JsonResponse({'success': False, 'error': 'Missing name'}, status=400)
        cat, created = Category.objects.get_or_create(name=name)
        return JsonResponse({'success': True, 'id': cat.id, 'name': cat.name})
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)


@login_required
def categories_api(request):
    cats = list(Category.objects.all().order_by('name').values('id', 'name'))
    return JsonResponse({'categories': cats})

@login_required
def invoice(request, transaction_id):
    sale = get_object_or_404(Sales, transaction_id=transaction_id)
    return render(request, 'store/invoice.html', {'sale': sale})

@login_required
def reports(request):
    # Simple reporting logic
    # sales_data used by original server-rendered table as fallback
    sales_data = Sales.objects.values('date_added__date').annotate(total=Sum('total_amount')).order_by('-date_added__date')
    return render(request, 'store/reports.html', {'sales_data': sales_data})


@login_required
def reports_data(request):
    # API endpoint returning aggregated sales data in JSON
    start = request.GET.get('start_date')
    end = request.GET.get('end_date')
    granularity = request.GET.get('granularity', 'daily')

    qs = Sales.objects.all()
    if start:
        try:
            start_dt = datetime.datetime.strptime(start, '%Y-%m-%d')
            qs = qs.filter(date_added__date__gte=start_dt.date())
        except Exception:
            pass
    if end:
        try:
            end_dt = datetime.datetime.strptime(end, '%Y-%m-%d')
            qs = qs.filter(date_added__date__lte=end_dt.date())
        except Exception:
            pass

    if granularity == 'weekly':
        data = qs.annotate(period=TruncWeek('date_added')).values('period').annotate(total=Sum('total_amount')).order_by('period')
    elif granularity == 'monthly':
        data = qs.annotate(period=TruncMonth('date_added')).values('period').annotate(total=Sum('total_amount')).order_by('period')
    else:
        data = qs.annotate(period=TruncDay('date_added')).values('period').annotate(total=Sum('total_amount')).order_by('period')

    # prepare response lists
    labels = []
    totals = []
    for item in data:
        p = item.get('period')
        if p is None:
            continue
        labels.append(p.strftime('%Y-%m-%d'))
        totals.append(float(item.get('total') or 0))

    # data accuracy verification (sum check)
    grand_total = sum(totals)

    return JsonResponse({'labels': labels, 'totals': totals, 'grand_total': grand_total})


@login_required
def reports_export(request):
    # export CSV (Excel-compatible) for a given date range and granularity
    start = request.GET.get('start_date')
    end = request.GET.get('end_date')
    granularity = request.GET.get('granularity', 'daily')

    # reuse reports_data logic by assembling queryset
    qs = Sales.objects.all()
    if start:
        try:
            start_dt = datetime.datetime.strptime(start, '%Y-%m-%d')
            qs = qs.filter(date_added__date__gte=start_dt.date())
        except Exception:
            pass
    if end:
        try:
            end_dt = datetime.datetime.strptime(end, '%Y-%m-%d')
            qs = qs.filter(date_added__date__lte=end_dt.date())
        except Exception:
            pass

    if granularity == 'weekly':
        data = qs.annotate(period=TruncWeek('date_added')).values('period').annotate(total=Sum('total_amount')).order_by('period')
        period_label = 'Week'
    elif granularity == 'monthly':
        data = qs.annotate(period=TruncMonth('date_added')).values('period').annotate(total=Sum('total_amount')).order_by('period')
        period_label = 'Month'
    else:
        data = qs.annotate(period=TruncDay('date_added')).values('period').annotate(total=Sum('total_amount')).order_by('period')
        period_label = 'Date'

    import csv
    from io import StringIO

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow([period_label, 'Total Sales'])
    for item in data:
        p = item.get('period')
        if p is None:
            continue
        writer.writerow([p.strftime('%Y-%m-%d'), float(item.get('total') or 0)])

    resp = HttpResponse(buf.getvalue(), content_type='text/csv')
    filename = f"sales_report_{granularity}_{start or 'all'}_{end or 'all'}.csv"
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp

def logout_user(request):
    logout(request)
    return redirect('login')
