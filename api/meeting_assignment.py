# import calendar
# from datetime import datetime, date, timedelta
# from django.db.models import Q
# from django.utils.timezone import now
# from accounts.models import User, MeetingEligibility
# from .models import Meeting, MeetingParticipant


# def assign_to_user(meeting_data):
#     department = meeting_data["department"]
#     meeting_type = meeting_data["meeting_type"].lower()
#     meeting_date = meeting_data["date"]
#     start_time = meeting_data["start_time"]
#     end_time = meeting_data["end_time"]

#     eligibilities = MeetingEligibility.objects.filter(
#         departments__contains=[department.id],
#         priority__isnull=False
#     )

#     if meeting_type == "w2":
#         eligibilities = eligibilities.filter(can_take_w2=True)
#     elif meeting_type == "contract":
#         eligibilities = eligibilities.filter(can_take_contract=True)

#     if not eligibilities.exists():
#         return None

#     highest_priority = eligibilities.order_by("-priority").first().priority
#     top_eligibilities = eligibilities.filter(priority=highest_priority)

#     if top_eligibilities.count() > 1:
#         week_start = meeting_date - timedelta(days=meeting_date.weekday())
#         week_end = week_start + timedelta(days=6)

#         scored_users = []
#         for elig in top_eligibilities:
#             user = elig.user
#             meeting_count = Meeting.objects.filter(
#                 participants__user=user,
#                 date__gte=week_start,
#                 date__lte=week_end
#             ).count()
#             print("User:", user.email, "Meetings this week:", meeting_count)
#             score = meeting_count * elig.priority
#             print("Score for user:", user.email, "is", score)
#             scored_users.append((user, score))

#         scored_users.sort(key=lambda x: x[1])
#         candidate_user = scored_users[0][0]
#     else:
#         candidate_user = top_eligibilities.first().user

#     has_conflict = Meeting.objects.filter(
#         participants__user=candidate_user,
#         date=meeting_date,
#         participants__is_to=True,
#         participants__is_active=True
#     ).filter(
#         Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
#     ).exists()

#     if has_conflict:
#         remaining = [elig.user for elig in top_eligibilities if elig.user != candidate_user]
#         for user in remaining:
#             conflict = Meeting.objects.filter(
#                 participants__user=user,
#                 date=meeting_date,
#                 participants__is_to=True,
#                 participants__is_active=True
#             ).filter(
#                 Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
#             ).exists()
#             if not conflict:
#                 return user
#         return None
#     return candidate_user




import calendar
from datetime import datetime, date, timedelta
from django.db.models import Q
from django.utils.timezone import now
from accounts.models import User, MeetingEligibility
from .models import Meeting, MeetingParticipant


def assign_to_user(meeting_data):
    department = meeting_data["department"]
    meeting_type = meeting_data["meeting_type"].lower()
    meeting_date = meeting_data["date"]
    start_time = meeting_data["start_time"]
    end_time = meeting_data["end_time"]

    # --- Get eligible users ---
    eligibilities = MeetingEligibility.objects.filter(
        departments__contains=[department.id],
        priority__isnull=False
    )
    print("[assign_to_user] initial eligibilities count:", eligibilities.count())

    if meeting_type == "w2":
        eligibilities = eligibilities.filter(can_take_w2=True)
    elif meeting_type == "contract":
        eligibilities = eligibilities.filter(can_take_contract=True)

    print(f"[assign_to_user] after type filter ({meeting_type}):", eligibilities.count())

    # Only consider users who have linked their Google account
    eligibilities = eligibilities.filter(user__google_linked=True)

    if not eligibilities.exists():
        return None

    # Define the week window for fairness calculation
    week_start = meeting_date - timedelta(days=meeting_date.weekday())
    week_end = week_start + timedelta(days=6)

    print(f"[assign_to_user] week window: {week_start} - {week_end}")

    scored_users = []
    for elig in eligibilities:
        user = elig.user
        print(f"[assign_to_user] evaluating user: {user.email} (priority={elig.priority})")
        meeting_count = Meeting.objects.filter(
            participants__user=user,
            date__gte=week_start,
            date__lte=week_end
        ).count()

        # Base fairness score
        fairness_score = meeting_count / elig.priority if elig.priority > 0 else float("inf")

        # Tie-breaker: meeting_count * priority
        tie_breaker = meeting_count * elig.priority

    scored_users.append((user, fairness_score, tie_breaker, elig.priority))
    print(f"[assign_to_user] user={user.email} fairness_score={fairness_score} tie_breaker={tie_breaker}")

    # --- Multi-level sort ---
    # 1. Lowest fairness_score wins
    # 2. If tie, lowest tie_breaker wins
    # 3. If still tie (initial calls), highest priority wins
    scored_users.sort(key=lambda x: (x[1], x[2], -x[3]))

    candidate_user = scored_users[0][0]

    # --- Conflict check ---
    has_conflict = Meeting.objects.filter(
        participants__user=candidate_user,
        date=meeting_date,
        participants__is_to=True,
        participants__is_active=True
    ).filter(
        Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
    ).exists()

    print(f"[assign_to_user] candidate={candidate_user.email} has_conflict={has_conflict}")

    if has_conflict:
        # Try remaining sorted users
        for user, _, _, _ in scored_users[1:]:
            conflict = Meeting.objects.filter(
                participants__user=user,
                date=meeting_date,
                participants__is_to=True,
                participants__is_active=True
            ).filter(
                Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
            ).exists()
            print(f"[assign_to_user] user={user.email} conflict={conflict}")
            if not conflict:
                return user
        return None

    return candidate_user
