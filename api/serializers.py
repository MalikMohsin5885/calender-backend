from rest_framework import serializers
from .models import Meeting, MeetingMember
from django.contrib.auth import get_user_model

User = get_user_model()

class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']

class MeetingSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    member_ids = serializers.ListField(
        write_only=True, child=serializers.IntegerField(), required=False
    )

    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'date', 'start_time', 'end_time',
            'created_by', 'members', 'member_ids'
        ]
        read_only_fields = ['id', 'created_by', 'members']

    def get_members(self, obj):
        members = User.objects.filter(meeting_participations__meeting=obj)
        return MemberSerializer(members, many=True).data

    def update(self, instance, validated_data):
        member_ids = validated_data.pop("member_ids", None)

        # Update regular fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if member_ids is not None:
            # Remove creator from member_ids if present
            if instance.created_by.id in member_ids:
                member_ids.remove(instance.created_by.id)

            users = list(User.objects.filter(id__in=member_ids))
            # Remove all existing members
            instance.memberships.all().delete()
            # Add new ones
            MeetingMember.objects.bulk_create([
                MeetingMember(meeting=instance, user=user) for user in users
            ])

        return instance


