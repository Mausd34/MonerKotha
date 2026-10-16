from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Category, DeletionRequest, Report, Story
from .services import contains_contact_details


class StorySubmissionForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="Leave this field empty")
    consent_given = forms.BooleanField(
        required=True,
        label="আমি কমিউনিটি নির্দেশিকা পড়েছি এবং প্রকাশের আগে মডারেশন হবে—এতে সম্মতি দিচ্ছি।",
        error_messages={"required": "জমা দিতে আপনার সম্মতি প্রয়োজন।"},
    )

    class Meta:
        model = Story
        fields = ("category", "content", "consent_given")
        widgets = {
            "category": forms.Select(
                attrs={"class": "field-control", "aria-describedby": "category-help category-errors"}
            ),
            "content": forms.Textarea(
                attrs={
                    "rows": 7,
                    "maxlength": 3000,
                    "placeholder": "নাম বা পরিচয় প্রকাশ না করে, আপনার অনুভূতির গল্পটি লিখুন…",
                    "class": "field-control",
                    "aria-describedby": "content-help content-errors",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["category"].empty_label = "বিষয় বেছে নিন"

    def clean_website(self):
        value = self.cleaned_data["website"]
        if value:
            raise ValidationError("আপনার জমা গ্রহণ করা যায়নি।")
        return value

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if contains_contact_details(content):
            raise ValidationError("নিরাপত্তার জন্য ইমেইল, ফোন নম্বর বা ওয়েব ঠিকানা বাদ দিন।")
        return content

    def save(self, commit=True):
        story = super().save(commit=False)
        story.status = Story.Status.PENDING
        story.created_at = timezone.now()
        if commit:
            story.save()
        return story


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ("reason", "details")
        widgets = {
            "reason": forms.Select(attrs={"class": "field-control"}),
            "details": forms.Textarea(attrs={"rows": 3, "maxlength": 500, "class": "field-control"}),
        }


class DeletionRequestForm(forms.Form):
    story_public_id = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 500, "class": "field-control"}),
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="Leave this field empty")

    def clean_website(self):
        value = self.cleaned_data["website"]
        if value:
            raise ValidationError("আপনার অনুরোধ গ্রহণ করা যায়নি।")
        return value
