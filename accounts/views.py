from django.contrib.auth.models import User
from django.db import IntegrityError
from django.shortcuts import render
from .forms import RegistrationForm


def register(request):
    user = None
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.create_user(
                    form.cleaned_data['email_address'],
                    form.cleaned_data['email_address']
                )
            except IntegrityError:
                user = User.objects.filter(username=form.cleaned_data['email_address']).first()
                pass
            form = None
    else:
        form = RegistrationForm()

    return render(request, 'register.html', {
        'form': form,
        'user': user
    })
