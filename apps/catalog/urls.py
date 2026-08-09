from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.ProductListView.as_view(), name="products"),
    path("products/<str:slug>/", views.product_detail, name="product_detail"),
    path("products/<str:slug>/review/", views.add_review, name="add_review"),
    path("products/<str:slug>/wishlist/", views.toggle_wishlist, name="toggle_wishlist"),
    path("compare/", views.compare, name="compare"),
    path("search/suggest/", views.search_suggest, name="search_suggest"),
    path("page/about/", views.about, name="about"),
    path("page/contact/", views.contact, name="contact"),
]
