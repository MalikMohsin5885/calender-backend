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
            'participants', 'to_id', 'cc_ids', 'remarks', 'jd_link', 'resume_link'
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

        # Step 1: Validate users BEFORE creating the meeting
        all_ids = set(filter(None, [to_id] + cc_ids))  # Filter out None values
        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = all_ids - found_ids
        if missing_ids:
            raise serializers.ValidationError({"detail": f"User(s) {missing_ids} not found."})

        # Step 2: Auto-assign logic if to_id is not given
        if not to_id:
            dept_users = User.objects.filter(department=validated_data['department'], priority__isnull=False).order_by('priority')
            if not dept_users.exists():
                raise serializers.ValidationError({"detail": "No users found in department to assign as 'to'."})
            to_user = dept_users.first()
            to_id = to_user.id

            if to_user.supervisor and to_user.supervisor.id != to_user.id:
                cc_ids.append(to_user.supervisor.id)

            # Re-validate with new cc_ids if necessary
            all_ids = set(filter(None, [to_id] + cc_ids))
            users = User.objects.filter(id__in=all_ids)
            found_ids = {u.id for u in users}
            missing_ids = all_ids - found_ids
            if missing_ids:
                raise serializers.ValidationError({"detail": f"User(s) {missing_ids} not found after auto-assign."})

        # Step 3: Now that validation is done, create the meeting
        meeting = Meeting.objects.create(**validated_data)

        # Step 4: Create participants (with versioning)
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