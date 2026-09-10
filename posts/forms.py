from django import forms
from .models import Post
from .validation import MEDIA_TYPES, validate_media_upload


class PostCreateForm(forms.ModelForm):
    media_type = forms.ChoiceField(
        choices=[(media_type, media_type.title()) for media_type in MEDIA_TYPES],
        widget=forms.RadioSelect,
        required=False,
        initial='image',
    )

    class Meta:
        model = Post
        fields = ('media_type', 'image', 'video', 'audio', 'document', 'caption')
        widgets = {
            'caption': forms.Textarea(attrs={
                'rows': 3, 'placeholder': 'Write a caption... use #hashtags to tag your post',
                'maxlength': 2200, 'class': 'input',
            }),
            'image': forms.ClearableFileInput(attrs={'class': 'js-post-media-input', 'accept': '.jpg,.jpeg,.png,.webp,.gif'}),
            'video': forms.ClearableFileInput(attrs={'class': 'js-post-media-input', 'accept': '.mp4,.webm,.mov'}),
            'audio': forms.ClearableFileInput(attrs={'class': 'js-post-media-input', 'accept': '.mp3,.wav,.m4a'}),
            'document': forms.ClearableFileInput(attrs={'class': 'js-post-media-input', 'accept': '.pdf,.docx,.xlsx,.txt,.csv'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        media_type = cleaned_data.get('media_type') or 'image'
        cleaned_data['media_type'] = media_type
        if media_type not in MEDIA_TYPES:
            return cleaned_data

        uploaded_fields = {
            field_name: cleaned_data.get(field_name)
            for field_name in ('image', 'video', 'audio', 'document')
        }
        selected = uploaded_fields.get(media_type)
        for field_name, uploaded in uploaded_fields.items():
            if uploaded and field_name != media_type:
                self.add_error(field_name, 'Selected file does not match the selected media type.')
        if not selected:
            self.add_error(media_type, f'Please select a {media_type} file.')
        else:
            try:
                validate_media_upload(media_type, selected)
            except forms.ValidationError as exc:
                self.add_error(media_type, exc)
        return cleaned_data


class PostEditForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('caption',)
        widgets = {
            'caption': forms.Textarea(attrs={'rows': 3, 'maxlength': 2200, 'class': 'input'}),
        }
