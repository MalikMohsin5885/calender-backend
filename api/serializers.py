from rest_framework import serializers
from .models import Meeting, MeetingParticipant
from django.contrib.auth import get_user_model
from django.db.models import Max

User = get_user_model()

class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']

class MeetingSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField(read_only=True)
    to_id = serializers.IntegerField(write_only=True, required=False)
    cc_ids = serializers.ListField(write_only=True, child=serializers.IntegerField(), required=False)

    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'date', 'start_time', 'end_time',
            'meeting_type', 'department', 'created_by', 'created_at',
            'participants', 'to_id', 'cc_ids'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'participants']

    def get_participants(self, obj):
        active_participants = obj.participants.filter(is_active=True)
        return [
            {
                'user': MemberSerializer(p.user).data,
                'is_to': p.is_to,
                'version': p.version,
                'updated_by': p.updated_by.name if p.updated_by else None
            }
            for p in active_participants
        ]

    def create(self, validated_data):
        request = self.context['request']
        to_id = validated_data.pop('to_id', None)
        cc_ids = validated_data.pop('cc_ids', [])

        meeting = Meeting.objects.create(**validated_data)

        # --- Auto assign logic remains same ---
        dept_users = User.objects.filter(department=meeting.department, priority__isnull=False).order_by('priority')
        if not to_id:
            if not dept_users.exists():
                raise serializers.ValidationError({"detail": "No users found in department to assign as 'to'."})
            to_user = dept_users.first()
            to_id = to_user.id

            if to_user.supervisor and to_user.supervisor.id != to_user.id:
                cc_ids.append(to_user.supervisor.id)

        # Validate users
        all_ids = set([to_id] + cc_ids)
        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = all_ids - found_ids
        if missing_ids:
            raise serializers.ValidationError({"detail": f"User(s) {missing_ids} not found."})

        max_version = MeetingParticipant.objects.filter(meeting=meeting).aggregate(max=Max('version'))['max'] or 0
        new_version = max_version + 1

        MeetingParticipant.objects.create(
            meeting=meeting,
            user=User.objects.get(id=to_id),
            is_to=True,
            version=new_version,
            is_active=True,
            updated_by=request.user
        )

        MeetingParticipant.objects.bulk_create([
            MeetingParticipant(
                meeting=meeting,
                user=user,
                is_to=False,
                version=new_version,
                is_active=True,
                updated_by=request.user
            )
            for user in users if user.id in cc_ids
        ])

        return meeting
