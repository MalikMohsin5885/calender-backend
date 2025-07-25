from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max
from .models import Meeting, MeetingParticipant
from .serializers import MeetingSerializer
from accounts.permissions import IsSupervisorOrBD
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date

from accounts.serializers import UserSerializer

User = get_user_model()

class MeetingListCreateView(generics.ListCreateAPIView):
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        date_param = self.request.query_params.get('date')
        queryset = Meeting.objects.all()

        # Filter by date if provided
        if date_param:
            try:
                date = parse_date(date_param)
                if date:
                    queryset = queryset.filter(start_time__date=date)
            except ValueError:
                pass  # ignore invalid date formats

        if user.has_permission("meeting.view_all_meetings"):
            print("User has permission to view all meetings")
            return queryset
        elif user.has_permission("meeting.view_own_meetings"):
            print("User has permission to view own meetings")
            return queryset.filter(created_by=user)
        elif user.has_permission("meeting.view_assigned_meetings"):
            print("User has permission to view assigned meetings")
            return queryset.filter(participants__user=user, participants__is_active=True)

        return Meeting.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class MeetingUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated, IsSupervisorOrBD]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data
        to_ids = data.get('to_ids', [])
        cc_ids = data.get('cc_ids', [])
        all_ids = list(set(to_ids + cc_ids))

        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = set(all_ids) - found_ids
        if missing_ids:
            return Response({"error": f"User(s) {missing_ids} not found."}, status=400)

        # Deactivate previous participants
        MeetingParticipant.objects.filter(meeting=instance, is_active=True).update(is_active=False)

        # Determine version
        max_version = MeetingParticipant.objects.filter(meeting=instance).aggregate(Max('version'))['version__max'] or 0
        new_version = max_version + 1

        # Create new participant entries
        MeetingParticipant.objects.bulk_create([
            MeetingParticipant(
                meeting=instance,
                user=u,
                is_to=(u.id in to_ids),
                version=new_version,
                is_active=True,
                updated_by=request.user
            ) for u in users
        ])

        # Update meeting core fields
        return super().update(request, *args, **kwargs)
    
    

User = get_user_model()

class UsersListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
