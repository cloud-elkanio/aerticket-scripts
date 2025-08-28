from rest_framework import serializers
from .models import Gallery
from users.models import Organization

class GallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = Gallery
        fields = ['id','name', 'alternative_text','url', 'module']
        

    def validate_module(self, value):
        module_choices = [choice[0] for choice in Gallery.module_choices]
        if value not in module_choices:
            raise serializers.ValidationError("Invalid module choice.")
        return value


    def update(self, instance, validated_data):
        validated_data.pop('url', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class GalleryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gallery
        fields = ['id','name', 'alternative_text', 'module']


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'organization_name','easy_link_billing_code']  
