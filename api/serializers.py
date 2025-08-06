from rest_framework import serializers
from .models import Meeting, MeetingParticipant
from django.contrib.auth import get_user_model
from django.db.models import Max

User = get_user_model()

class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']

class MeetingParticipantSerializer(serializers.ModelSerializer):
    user = MemberSerializer()

    class Meta:
        model = MeetingParticipant
        fields = ['user', 'is_to', 'version', 'updated_by']

class MeetingSerializer(serializers.ModelSerializer):
    to_participant = serializers.SerializerMethodField()
    other_participants = serializers.SerializerMethodField()

    # Make created_by read-only (so it's not required in request body)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    # Add these fields to support participant logic in the request body
    to_id = serializers.IntegerField(write_only=True, required=False)
    cc_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'date', 'start_time', 'end_time',
            'meeting_type', 'department', 'created_by', 'created_at',
            'to_participant', 'other_participants',
            'remarks', 'jd_link', 'resume_link',
            'to_id', 'cc_ids',  # Include these in serializer for input
        ]

    def get_to_participant(self, obj):
        to_part = obj.participants.filter(is_to=True, is_active=True).first()
        if to_part:
            return MeetingParticipantSerializer(to_part).data
        return None

    def get_other_participants(self, obj):
        others = obj.participants.filter(is_to=False, is_active=True)
        return MeetingParticipantSerializer(others, many=True).data

    def create(self, validated_data):
        request = self.context['request']
        to_id = validated_data.pop('to_id', None)
        cc_ids = validated_data.pop('cc_ids', [])

        # Set authenticated user as creator
        validated_data['created_by'] = request.user

        all_ids = set(filter(None, [to_id] + cc_ids))
        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = all_ids - found_ids
        if missing_ids:
            raise serializers.ValidationError({"detail": f"User(s) {missing_ids} not found."})

        if not to_id:
            dept_users = User.objects.filter(department=validated_data['department'], priority__isnull=False).order_by('priority')
            if not dept_users.exists():
                raise serializers.ValidationError({"detail": "No users found in department to assign as 'to'."})
            to_user = dept_users.first()
            to_id = to_user.id

            if to_user.supervisor and to_user.supervisor.id != to_user.id:
                cc_ids.append(to_user.supervisor.id)

            all_ids = set(filter(None, [to_id] + cc_ids))
            users = User.objects.filter(id__in=all_ids)
            found_ids = {u.id for u in users}
            missing_ids = all_ids - found_ids
            if missing_ids:
                raise serializers.ValidationError({"detail": f"User(s) {missing_ids} not found after auto-assign."})

        meeting = Meeting.objects.create(**validated_data)

        max_version = MeetingParticipant.objects.filter(meeting=meeting).aggregate(max=Max('version'))['max'] or 0
        new_version = max_version + 1

        # To participant
        to_user = User.objects.get(id=to_id)
        MeetingParticipant.objects.create(
            meeting=meeting,
            user=to_user,
            is_to=True,
            version=new_version,
            is_active=True,
            updated_by=request.user
        )

        # CC participants
        cc_users = [u for u in users if u.id in cc_ids]
        MeetingParticipant.objects.bulk_create([
            MeetingParticipant(
                meeting=meeting,
                user=user,
                is_to=False,
                version=new_version,
                is_active=True,
                updated_by=request.user
            )
            for user in cc_users
        ])
        return meeting
