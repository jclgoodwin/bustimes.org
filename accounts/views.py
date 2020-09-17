from django.contrib.auth import get_user_model, views as auth_views
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .forms import RegistrationForm

UserModel = get_user_model()


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save(request=request)
    else:
        form = RegistrationForm()

    return render(request, 'register.html', {
        'form': form,
    })


class RegisterConfirmView(auth_views.PasswordResetConfirmView):
    pass


class LoginView(auth_views.LoginView):
    pass


class PasswordResetView(auth_views.PasswordResetView):
    pass


def user_detail(request, pk):
    user = get_object_or_404(UserModel, pk=pk)

    revisions = user.vehiclerevision_set.select_related('vehicle', 'from_operator', 'to_operator')
    revisions = revisions.order_by('-id')
    paginator = Paginator(revisions, 100)
    page = request.GET.get('page')

    return render(request, 'user_detail.html', {
        'object': user,
        'revisions': paginator.get_page(page)
    })
