from rest_framework import serializers
from .models import Meeting, MeetingParticipant
from django.contrib.auth import get_user_model
from django.db.models import Max

User = get_user_model()

def times_overlap(start1, end1, start2, end2):
    """Return True if two time ranges overlap."""
    return start1 < end2 and start2 < end1

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

    created_by = serializers.CharField(source="created_by.name", read_only=True)

    to_id = serializers.IntegerField(write_only=True, required=False)
    cc_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'date', 'start_time', 'end_time',
            'meeting_type', 'department', 'created_by', 'created_at',
            'to_participant', 'other_participants',
            'remarks', 'jd_link', 'resume_link',
            'to_id', 'cc_ids',
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

        validated_data['created_by'] = request.user

        all_ids = set(filter(None, [to_id] + cc_ids))
        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = all_ids - found_ids
        if missing_ids:
            raise serializers.ValidationError({"detail": f"User(s) {missing_ids} not found."})

        # Auto-assign to_id if not provided
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

        # ====== NEW LOGIC: Check for time conflict for "to" user ======
        meeting_date = validated_data['date']
        start_time = validated_data['start_time']
        end_time = validated_data['end_time']

        existing_meetings = Meeting.objects.filter(
            participants__user_id=to_id,
            participants__is_to=True,
            participants__is_active=True,
            date=meeting_date
        )

        for m in existing_meetings:
            if times_overlap(start_time, end_time, m.start_time, m.end_time):
                to_user_name = User.objects.get(id=to_id).name
                raise serializers.ValidationError({
                    "detail": f"User '{to_user_name}' already has a meeting from {m.start_time} to {m.end_time} on {meeting_date}. Please choose a different time."
                })
        # ====== END NEW LOGIC ======

        meeting = Meeting.objects.create(**validated_data)

        max_version = MeetingParticipant.objects.filter(meeting=meeting).aggregate(max=Max('version'))['max'] or 0
        new_version = max_version + 1

        to_user = User.objects.get(id=to_id)
        MeetingParticipant.objects.create(
            meeting=meeting,
            user=to_user,
            is_to=True,
            version=new_version,
            is_active=True,
            updated_by=request.user
        )

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
