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
    member_ids = serializers.ListField(write_only=True, child=serializers.IntegerField(), required=False)

    class Meta:
        model = Meeting
        fields = ['id', 'title', 'description', 'start_time', 'end_time', 'created_by', 'members', 'member_ids']
        read_only_fields = ['id', 'created_by', 'members']

    def get_members(self, obj):
        members = User.objects.filter(meeting_participations__meeting=obj)
        return MemberSerializer(members, many=True).data
