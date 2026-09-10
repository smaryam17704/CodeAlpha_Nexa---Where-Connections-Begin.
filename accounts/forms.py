from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm
from .models import Profile, Interest

User = get_user_model()

SKIP_WIDGETS = (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect, forms.FileInput)


class StyledFormMixin:
    """Applies the shared `.input` CSS class to text-like widgets automatically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, SKIP_WIDGETS):
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' input').strip()


class SignUpForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class ProfileSetupForm(StyledFormMixin, forms.ModelForm):
    display_name = forms.CharField(max_length=80, required=True)
    username = forms.CharField(max_length=150, required=True)

    class Meta:
        model = Profile
        fields = ('display_name', 'avatar', 'bio')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'maxlength': 200, 'placeholder': 'Tell people about yourself'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['username'].initial = self.user.username

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.username = self.cleaned_data['username']
        if commit:
            self.user.save()
            profile.save()
        return profile


class InterestSelectionForm(forms.Form):  # checkboxes styled manually in template
    interests = forms.ModelMultipleChoiceField(
        queryset=Interest.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )


class ProfileEditForm(StyledFormMixin, forms.ModelForm):
    username = forms.CharField(max_length=150, required=True)

    class Meta:
        model = Profile
        fields = ('display_name', 'username', 'bio', 'avatar')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'maxlength': 200}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['username'].initial = self.user.username

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.username = self.cleaned_data['username']
        if commit:
            self.user.save()
            profile.save()
        return profile


class StyledAuthenticationForm(StyledFormMixin, AuthenticationForm):
    pass


class StyledPasswordResetForm(StyledFormMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    pass
