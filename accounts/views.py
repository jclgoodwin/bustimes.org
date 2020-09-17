from django.shortcuts import render
from django.contrib.auth import views as auth_views
from .forms import RegistrationForm


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
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'].fields['username'].label = 'Email address'
        context['form'].fields['username'].widget.input_type = 'email'
        return context


class PasswordResetView(auth_views.PasswordResetView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'].fields['email'].label = 'Email address'
        return context
