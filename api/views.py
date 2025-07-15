from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Meeting, MeetingMember
from .serializers import MeetingSerializer

User = get_user_model()

class MeetingListCreateView(generics.ListCreateAPIView):
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        user_perms = set(user.get_permissions())

        if 'meeting.view_all_meetings' in user_perms:
            return Meeting.objects.all()
        elif 'meeting.view_own_meetings' in user_perms:
            return Meeting.objects.filter(created_by=user)
        elif 'meeting.view_assigned_meetings' in user_perms:
            return Meeting.objects.filter(memberships__user=user)
        return Meeting.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user
        if 'meeting.schedule_meeting' not in user.get_permissions():
            return Response({"detail": "You do not have permission to schedule meetings."}, status=403)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        member_ids = data.get('member_ids', [])
        if user.id in member_ids:
            member_ids.remove(user.id)

        users = list(User.objects.filter(id__in=member_ids))
        found_ids = {u.id for u in users}
        missing_ids = set(member_ids) - found_ids

        if missing_ids:
            return Response(
                {"error": f"User(s) with ID(s) {list(missing_ids)} not found."},
                status=status.HTTP_400_BAD_REQUEST
            )

        meeting = Meeting.objects.create(
            title=data['title'],
            description=data['description'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            created_by=user
        )

        MeetingMember.objects.bulk_create([
            MeetingMember(meeting=meeting, user=u) for u in users
        ])

        return Response({"message": "Meeting created successfully."}, status=status.HTTP_201_CREATED)
