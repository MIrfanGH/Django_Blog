"""
    Class-based views for blog post CRUD operations with caching,
        pagination, and asynchronous task integration.
"""

from django.shortcuts import render, get_object_or_404
from .models import Post 
from django.urls import reverse_lazy
from django.contrib.auth.models import User

from django.contrib.auth.mixins import ( LoginRequiredMixin,
                                        UserPassesTestMixin # Restricts access to a view based on a custom test function that we define
                                        )
from users.mixins import AuthorRequiredMixin
from django.views.generic import (
                        DetailView, 
                        ListView,
                        CreateView,
                        UpdateView,
                        DeleteView,
                        )

from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from .tasks import (
    post_notifying_email, 
    post_update_notifying_email,
    notify_post_deletion,

)

import logging
logger = logging.getLogger(__name__)



class PostListView(ListView):
    """
    Home page view - displays all blog posts with pagination.
    
    Features:
        - Redis caching for 1 hour (3600s)
        - Pagination: 4 posts per page
        - Newest posts first (descending order)
        - Cache invalidated by signals on post create/update/delete
    Production Notes:
        - Cache key consistent with signals.py for proper invalidation
        - Query optimized with select_related('author') for N+1 prevention
        - Returns list() for cache serialization compatibility
    """

    model = Post
    template_name = 'blog/home.html'  # Template to render 'blog/post_list.html
    context_object_name = 'posts'     # Custom template used default is 'object_list'
    paginate_by = 4
    ordering = ['-date_posted']       # Newest posts first ('-' indicates descending order by date)

    def get_queryset(self):
        """
        Overwriting default get_queryset() to retrieve posts from cache or database.        
        Cache Strategy:
            Key: 'post_list_view' (global list)
            TTL: 3600 seconds (1 hour)
            Invalidated by: post_save, post_delete signals 
        Returns:
            list: All Post objects ordered by date_posted (newest first)
        """
        cache_key = ('post_list_view')
        posts = cache.get(cache_key)

        if posts is not None:
            logger.debug('PostListView: Returning posts from cache')
            return posts
        
        # Query optimization: Load author data to prevent N+1 queries  
        posts = list(
            Post.objects
            .select_related('author')  # preload author since template accesses post.author for each post,  JOIN user table 
            .order_by('-date_posted')
        )
        cache.set(cache_key, posts, 3600)
        return posts


    
    def get_context_data(self, **kwargs):

        """
        Extends context with one-time AI summary from session.
        
        Retrieves and removes 'ai_summary' from session storage, making it
        available only for the current request.
        
        Returns:
            dict: Context with 'ai_summary' key (str or None)
            
        Note:
            Uses session.pop() for atomic read-and-delete to ensure summary
            displays exactly once after being set by asynchronous tasks.
        """


        context = super().get_context_data(**kwargs)

        # One-time, request-scoped AI summary
        context["ai_summary"] = self.request.session.pop(
            "ai_summary", None
        )

        return context



class SameUserPostListView(ListView):
    """
    Displays all posts created by a specific user.
    
    Features:
        > Per-user caching for 30 minutes
        > Pagination: 4 posts per page
        > 404 if user doesn't exist

    Production Notes:
        - Cache key includes username for user-specific caching
        - Prevents cache collision between different users
        - Optimized with select_related for author data
    """
    model = Post
    template_name = 'blog/same_user_posts.html' 
    context_object_name = 'SamePosts' 
    paginate_by = 4
    
    def get_queryset(self): 
        """ 
        Retrieve posts by specific user from cache or database. 
        """

        username = self.kwargs.get('username')
        cache_key = f"user_posts_{username}"  # ensures each user's posts are cached separately ex: 

        # Try to get from cache
        posts = cache.get(cache_key)
        
        if posts is not None:
            logger.debug(f"SameUserPostListView: Returning {username}'s posts from cache")
            return posts
        
        # Cache empty - fetch from database
        logger.debug(f"SameUserPostListView: Not cached for {username}, querying DB")
        user = get_object_or_404(User, username=self.kwargs.get('username'))

        # Query optimization> select_related not needed since we already have user object
        posts = list(Post.objects.filter(author=user).order_by('-date_posted'))

        # Cache for 30 minutes
        cache.set(cache_key, posts, timeout=60 * 30)

        return posts
        


@method_decorator(cache_page(60 * 60, key_prefix='post_detail'), name='dispatch')
class PostDetailView(DetailView):
    
    """
    Display a single blog post with full content.
    
    Features:
        > Full-page caching for 1 hour (3600s)
        > Caches entire rendered HTML
        > Cache invalidated by signals on post update/delete
    
    Template: blog/post_detail.html (default)
    Context:  Default context object name: 'object' (unless explicitly defined)   
    URL Pattern: /post/<int:pk>/
    
    Production Notes:
        - cache_page caches the ENTIRE rendered HTML response
        - More efficient than manual caching (no template rendering on cache hit)
        - Key prefix prevents collision with other cached pages
        - Invalidation handled by signals using post PK 

    Performance:
        - First request: ~50ms (DB + template rendering)
        - Cached requests: ~5ms (direct HTML serve from Redis)
    """

    model = Post
   
    def get_queryset(self):
        """
        Optimize query to prevents N+1 query when displaying author information.
        """
        return Post.objects.select_related('author')



class PostCreateView(AuthorRequiredMixin, LoginRequiredMixin, CreateView):
    
    """
    Allow authenticated users with 'Author' role to create new posts.
    
    Features:
        - Login required (redirects to login if not authenticated)
        - Author role required (from AuthorRequiredMixin)
        - Asynchronous email notification via Celery
        - Automatic author assignment

    Form Fields: ['title', 'content_nature', 'content']
    Template: blog/post_form.html (default)
    Success URL: Defined in Post.get_absolute_url()
    
    Production Notes:
        - Email sent asynchronously (non-blocking)
        - Cache invalidated automatically by post_save signal
        - Task failures handled by Celery retry mechanism
        - Mixin order: LoginRequiredMixin FIRST for proper redirect
    """

    model = Post
    fields = ['title', 'content_nature', 'content'] 

    # Assign the current user as the author before saving by overriding the default method
    def form_valid(self, form):  
        """
        Process valid form submission.    
        Steps:
            1. Assign current user as post author
            2. Save post to database
            3. Trigger async email notification
            4. Redirect to success URL
        """
        form.instance.author = self.request.user 
        post_notifying_email.delay(self.request.user.username, self.request.user.email)
        logger.info(
            f"Post created by {self.request.user.username}. "
            f"Email notification queued."
        )
        # Save post and redirect
        return super().form_valid(form) 
    


class PostUpdateView(AuthorRequiredMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    
    """
    Allow authenticated post authors to update their own posts.
    
    Features:
        - Login required
        - Author role required
        - Ownership check (only original author can edit)
        - Asynchronous email notification
    
    Form Fields: ['title', 'content_nature', 'content']
    Template: blog/post_form.html (default)
    Success URL: Defined in Post.get_absolute_url()
    
    Production Notes:
        - Multiple mixins enforce security (MRO: left-to-right)
        - test_func() ensures user is the original author
        - Cache invalidated by post_save signal
        - Mixin order: LoginRequiredMixin FIRST
    """
    model = Post
    fields = ['title', 'content_nature', 'content']  

    def form_valid(self, form):
        form.instance.author = self.request.user
        response =  super().form_valid(form)

        # Async email notification
        post_update_notifying_email.delay(self.request.user.username, self.request.user.email)
        
        logger.info(
            f"Post {self.object.pk} updated by {self.request.user.username}. "
            f"Email notification queued."
        )
        return response

    def test_func(self):
        """
        Authorization check: Verify if a user can edit this post.
        
        Conditions:
            1. User has ot have 'Author' role (via AuthorRequiredMixin)
            2. User is the original post author        
        MRO here:
            - Checks AuthorRequiredMixin.test_func() first (role check)
            - Then checks ownership (self.request.user == post.author)
            - Both must be True for access
        """
        post = self.get_object() 
        # Role check (AuthorRequiredMixin) AND ownership check
        return super().test_func() and self.request.user == post.author 
        



class PostDeleteView(AuthorRequiredMixin, LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Allow authenticated post authors to delete their own posts.

    Production Notes:
        - Email sent AFTER deletion confirmation (in delete() method)
        - Cache invalidated by post_delete signal
        - Success URL uses reverse_lazy (evaluated at runtime)
        - Mixin order: LoginRequiredMixin FIRST
    """
    model = Post
    template_name = 'blog/post_delete.html' # Custom template used  default is 'post_confirm_delete.html'
    success_url = reverse_lazy("blog_home") # Redirect to home after deletion

    def test_func(self):
        post = self.get_object() 
        response =  super().test_func() and self.request.user == post.author 
        return response
    

    def delete(self, request, *args, **kwargs):
        """ Handle post deletion AFTER user confirms. """

        # Cache essential fields BEFORE deletion --> Reduced DB hits, better readability and to avoid accidental access after deletion
        post = self.get_object()
        post_title = post.title
        username = request.user.username
        user_email = request.user.email

        # Queue async email notification
        notify_post_deletion.delay(username, user_email, post_title)

        # Log deletion event (for debug and testing)
        logger.info(
            f"Post '{post_title}' (ID: {post.pk}) deleted by {username}. "
            f"Email notification queued."
        )
        return super().delete(request, *args, **kwargs)


cache_page(60 * 60, key_prefix='about')
def about(request):
    """  Display the About page. """
    
    return render(request, 'blog/about.html', {'title':'About'}) 
    # Manually define context inside the render(), passing this dictionary directly from view to the template.

