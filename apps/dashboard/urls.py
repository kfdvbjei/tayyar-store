from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    # المبيعات
    path("orders/", views.order_list, name="orders"),
    path("orders/<str:number>/", views.order_detail, name="order_detail"),
    # المنتجات
    path("products/", views.product_list, name="products"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/toggle/", views.product_toggle, name="product_toggle"),
    # المخزون
    path("inventory/", views.inventory_list, name="inventory"),
    path("inventory/move/", views.stock_move, name="stock_move"),
    path("inventory/transfer/", views.stock_transfer, name="stock_transfer"),
    path("inventory/movements/", views.movement_log, name="movements"),
    path("warehouses/", views.warehouse_list, name="warehouses"),
    path("warehouses/new/", views.warehouse_create, name="warehouse_create"),
    path("warehouses/<int:pk>/edit/", views.warehouse_edit, name="warehouse_edit"),
    # المشتريات
    path("purchases/", views.purchase_list, name="purchases"),
    path("purchases/new/", views.purchase_create, name="purchase_create"),
    path("purchases/<int:pk>/", views.purchase_detail, name="purchase_detail"),
    path("purchases/<int:pk>/edit/", views.purchase_edit, name="purchase_edit"),
    path("purchases/<int:pk>/receive/", views.purchase_receive, name="purchase_receive"),
    path("suppliers/", views.supplier_list, name="suppliers"),
    path("suppliers/new/", views.supplier_create, name="supplier_create"),
    path("suppliers/<int:pk>/edit/", views.supplier_edit, name="supplier_edit"),
    # التقارير
    path("reports/", views.reports, name="reports"),
    path("reports/export/orders.csv", views.export_orders_csv, name="export_orders"),
    path("reports/export/stock.csv", views.export_stock_csv, name="export_stock"),
    path("api/sales-series/", views.sales_series, name="sales_series"),
]
