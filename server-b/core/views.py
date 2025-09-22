from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def server_a_user_guide(request):
    return render(request, 'core/server_a_user_guide.html')

