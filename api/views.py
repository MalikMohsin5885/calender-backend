from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max
from .models import Meeting, MeetingParticipant
from .serializers import MeetingSerializer
from accounts.permissions import IsSupervisorOrBD, IsSupervisor
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date
from accounts.models import Department, User, Role
from accounts.serializers import DepartmentSimpleSerializer, UserSimpleSerializer, UserListUpdateCreateSerializer
from rest_framework.views import APIView

User = get_user_model()

class MeetingListCreateView(generics.ListCreateAPIView):
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        date_param = self.request.query_params.get('date')
        queryset = Meeting.objects.all()

        if date_param:
            try:
                date = parse_date(date_param)
                if date:
                    queryset = queryset.filter(date=date)
            except ValueError:
                pass

        if user.has_permission("meeting.view_all_meetings"):
            return queryset
        elif user.has_permission("meeting.view_own_meetings"):
            return queryset.filter(created_by=user)
        elif user.has_permission("meeting.view_assigned_meetings"):
            return queryset.filter(participants__user=user, participants__is_active=True)

        return Meeting.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"detail": "Meeting created successfully."}, status=status.HTTP_201_CREATED)

class MeetingUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # Use your User model's has_permission method
        can_update_all = request.user.has_permission("meeting.update_all_meetings")
        can_update_own = request.user.has_permission("meeting.update_own_meetings")

        if not (can_update_all or (can_update_own and instance.created_by == request.user)):
            return Response(
                {"detail": "You do not have permission to update this meeting."},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data
        to_id = data.get("to_id")
        cc_ids = data.get("cc_ids", [])

        if not isinstance(cc_ids, list):
            return Response({"detail": "cc_ids must be a list."}, status=400)

        all_ids = list(set([to_id] + cc_ids)) if to_id else cc_ids
        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = set(all_ids) - found_ids

        if missing_ids:
            return Response({"detail": f"User(s) {missing_ids} not found."}, status=400)

        # Deactivate previous participants
        MeetingParticipant.objects.filter(meeting=instance, is_active=True).update(is_active=False)

        max_version = MeetingParticipant.objects.filter(meeting=instance).aggregate(Max("version"))["version__max"] or 0
        new_version = max_version + 1

        participants = []

        if to_id:
            to_user = get_object_or_404(User, id=to_id)
            participants.append(MeetingParticipant(
                meeting=instance,
                user=to_user,
                is_to=True,
                version=new_version,
                is_active=True,
                updated_by=request.user
            ))

        cc_users = [u for u in users if u.id in cc_ids]
        for user in cc_users:
            participants.append(MeetingParticipant(
                meeting=instance,
                user=user,
                is_to=False,
                version=new_version,
                is_active=True,
                updated_by=request.user
            ))

        MeetingParticipant.objects.bulk_create(participants)

        return super().update(request, *args, **kwargs)
    
    
    

class DepartmentAndUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        departments = Department.objects.all().only('id', 'name')
        department_data = DepartmentSimpleSerializer(departments, many=True).data

        closer_users = User.objects.filter(role__name='Closer').only('id', 'name', 'email')
        closers_data = UserSimpleSerializer(closer_users, many=True).data

        all_users = User.objects.all().only('id', 'name', 'email')
        all_users_data = UserSimpleSerializer(all_users, many=True).data

        return Response({
            "departments": department_data,
            "closers": closers_data,
            "all_users": all_users_data
        })
        
        
class UserListCreateUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsSupervisor]

    def get(self, request):
        users = User.objects.exclude(id=request.user.id)
        serializer = UserListUpdateCreateSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # def post(self, request):
    #     serializer = UserListUpdateCreateSerializer(data=request.data)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response({"detail": "User created successfully."}, status=status.HTTP_201_CREATED)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserListUpdateCreateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "User updated successfully.", "data": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)