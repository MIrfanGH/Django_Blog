from django.urls import path
from . import views
from .views import (
    PostListView, 
    PostDetailView,
    PostCreateView,
    PostUpdateView,
    PostDeleteView,
    SameUserPostListView,

)

urlpatterns = [

    # Home and static pages
    path('', PostListView.as_view(), name='blog_home'), # Home page - displays a list of all blog posts 
    path('about/', views.about, name='blog_about'),

    # Post CRUD operations
    path('post/create/', PostCreateView.as_view(), name='post_create'), # Create a new blog post
    path('post/<int:pk>/detail/', PostDetailView.as_view(), name='post_detail'),# Detailed view of a specific post by ID
    path('post/<int:pk>/update/', PostUpdateView.as_view(), name='post_update'),
    path('post/<int:pk>/delete/', PostDeleteView.as_view(), name='post_delete'),

    # User-specific posts
    path('user/<str:username>/posts/', SameUserPostListView.as_view(), name='same_user_posts'),


]

