from django.shortcuts import render, get_object_or_404
from .models import Post
from django.urls import reverse_lazy
from django.contrib.auth.models import User

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
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

 

class PostListView(ListView):
    """ Home Page View - List all posts """
    print("Getting the List from DB")
    model = Post
    template_name = 'blog/home.html'  # Template to render 'blog/post_list.html
    context_object_name = 'posts'     # Custom template used default is 'object_list'
    paginate_by = 4
    ordering = ['-date_posted']       # Newest posts first ('-' indicates descending order by date)

    def get_queryset(self):
        cache_key = ('post_list_view')
        posts = cache.get(cache_key)

        if posts is not None:
            print('Returning from Cache')
            return posts
        
        print('Returning from DB')
        posts = list(Post.objects.all().order_by('-date_posted'))
        cache.set(cache_key, posts, 60 * 60)
        return posts


class SameUserPostListView(ListView):
    """Displays posts created by a specific user"""
    model = Post
    template_name = 'blog/same_user_posts.html' 
    context_object_name = 'SamePosts' 
    paginate_by = 4
    
    def get_queryset(self):
        username = self.kwargs.get('username')
        cache_key = f"user_posts_{username}"  # ensures each user's posts are cached separately ex: 
        
        # Try to get from cache
        posts = cache.get(cache_key)
        
        if posts is not None:
            print(f"Getting posts for {username} from CACHE")
            return posts
        
        # Cache empty - fetch from database
        print(f"Getting posts for {username} from DB")
        user = get_object_or_404(User, username=self.kwargs.get('username'))
        posts = list(Post.objects.filter(author=user).order_by('-date_posted'))

        # Cache for 30 minutes
        cache.set(cache_key, posts, timeout=60 * 30)
        return posts
        

""" Manual caching here.............Because you'd only be replacing the database lookup but still rendering the template on every request. 
Page caching does both — it stores and serves the final HTML. That saves more time and more server resources. """
@method_decorator(cache_page(60 * 60, key_prefix='post_detail'), name='dispatch')
class PostDetailView(DetailView):
    """ Post Detail View - Shows a single post"""
    model = Post
    # Default template: blog/post_detail.html (unless explicitly defined)
    # Default context object name: 'object' (unless explicitly defined)




class PostCreateView(AuthorRequiredMixin, LoginRequiredMixin, CreateView):
    """Allows logged-in users to create a new post."""
    model = Post
    fields = ['title', 'content_nature', 'content'] 

    # Assign the current user as the author before saving by overriding the default method
    def form_valid(self, form):  
        form.instance.author = self.request.user 
        return super().form_valid(form) 
    


class PostUpdateView(AuthorRequiredMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Allows logged in users(authors) to update their own posts. """
    model = Post
    fields = ['title', 'content_nature', 'content']  

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)
    
    def test_func(self):
        # Allow update only if:
                            # 1. The user passes the role check from AuthorRequiredMixin (super().test_func()),   MRO and Mixins working matters here
                            # 2. The logged-in user is the original author of the post

        post = self.get_object() 
        return super().test_func() and self.request.user == post.author 
        



class PostDeleteView(AuthorRequiredMixin, LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Allows logged in authors to delete their own posts """
    model = Post
    template_name = 'blog/post_delete.html' # Custom template used  default is 'post_confirm_delete.html'
    success_url = reverse_lazy("blog_home") # Redirect to home after deletion

    def test_func(self):
        post = self.get_object() 
        return super().test_func() and self.request.user == post.author 
            


def about(request):

    return render(request, 'blog/about.html', {'title':'About'}) 
    # Manually define context inside the render(), passing this dictionary directly from view to the template.





