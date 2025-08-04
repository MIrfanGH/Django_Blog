from django.shortcuts import render, get_object_or_404
from .models import Post
from django.urls import reverse_lazy
from django.contrib.auth.models import User

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
                        DetailView, 
                        ListView,
                        CreateView,
                        UpdateView,
                        DeleteView,
                        )




class PostListView(ListView):
    """ Home Page View - List all posts """
    model = Post
    template_name = 'blog/home.html'  # Template to render 'blog/post_list.html
    context_object_name = 'posts'     # Custom template used default is 'object_list'
    paginate_by = 4
    ordering = ['-date_posted']       # Newest posts first ('-' indicates descending order by date)


class SameUserPostListView(ListView):
    """Displays posts created by a specific user"""
    model = Post
    template_name = 'blog/same_user_posts.html' 
    context_object_name = 'SamePosts' 
    paginate_by = 4
      
    def get_queryset(self):
        # Fetch user object using username from URL 
        user = get_object_or_404(User, username=self.kwargs.get('username'))
        return Post.objects.filter(author=user).order_by('-date_posted') 



class PostDetailView(DetailView):
    """ Post Detail View - Shows a single post"""
    model = Post
    # Default template: blog/post_detail.html (unless explicitly defined)
    # Default context object name: 'object' (unless explicitly defined)




class PostCreateView(LoginRequiredMixin, CreateView):
    """Allows logged-in users to create a new post."""
    model = Post
    fields = ['title', 'content_nature', 'content'] 

    # Assign the current user as the author before saving
    def form_valid(self, form):  
        form.instance.author = self.request.user 
        return super().form_valid(form) 
    


class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Allows logged in authors(users) to update their own posts. """
    model = Post
    fields = ['title', 'content_nature', 'content']  

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)
    
    def test_func(self):
        # Allow update only if the logged-in user is the author
        post = self.get_object() # will get the current post's instance
        return self.request.user == post.author



class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Allows logged in authors to delete their own posts """
    model = Post
    template_name = 'blog/post_delete.html' # Custom template used  default is 'post_confirm_delete.html'
    success_url = reverse_lazy("blog_home") # Redirect to home after deletion

    def test_func(self):
        post = self.get_object() 
        if self.request.user == post.author:
            return True 
        return False


def about(request):

    return render(request, 'blog/about.html', {'title':'About'}) 
    # Manually define context inside the render(), passing this dictionary directly from view to the template.





