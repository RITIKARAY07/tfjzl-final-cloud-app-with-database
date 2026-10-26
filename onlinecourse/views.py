
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from .models import Course, Enrollment, Question, Choice, Submission
import logging

logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        if User.objects.filter(username=username).exists():
            context['message'] = "User already exists."
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            password=password
        )
        login(request, user)
        return redirect('onlinecourse:index')


def login_request(request):
    context = {}

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')

        context['message'] = 'Invalid username or password.'

    return render(
        request,
        'onlinecourse/user_login_bootstrap.html',
        context
    )


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    if user.is_authenticated:
        return Enrollment.objects.filter(
            user=user,
            course=course
        ).exists()
    return False


class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            course.is_enrolled = check_if_enrolled(user, course)

        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_details_bootstrap.html'

def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)

    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    enrollment, created = Enrollment.objects.get_or_create(
        user=request.user,
        course=course,
        defaults={'mode': 'honor'}
    )

    if created:
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse(
            'onlinecourse:course_details',
            args=(course.id,)
        )
    )


def extract_answers(request):
    submitted_answers = []

    for key in request.POST:
        if key.startswith('choice_'):
            try:
                choice_id = int(request.POST[key])
                submitted_answers.append(choice_id)
            except (ValueError, TypeError):
                continue

    return submitted_answers


def submit(request, course_id):
    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    if request.method != 'POST':
        return redirect(
            'onlinecourse:course_details',
            pk=course_id
        )

    course = get_object_or_404(Course, pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    submitted_choice_ids = extract_answers(request)

    selected_choices = Choice.objects.filter(
        id__in=submitted_choice_ids,
        question__course=course
    )

    submission.choices.set(selected_choices)

    return HttpResponseRedirect(
        reverse(
            'onlinecourse:exam_result',
            args=(course.id, submission.id)
        )
    )


def show_exam_result(request, course_id, submission_id):
    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__course=course,
        enrollment__user=request.user
    )

    selected_choices = submission.choices.all()
    total_score = 0
    total_possible = 0
    question_results = []

    for question in course.question_set.all():
        correct_choices = question.choices.filter(
            is_correct=True
        )

        question_selected_choices = selected_choices.filter(
            question=question
        )

        correct_ids = set(
            correct_choices.values_list('id', flat=True)
        )

        selected_ids = set(
            question_selected_choices.values_list('id', flat=True)
        )

        is_correct = (
            len(correct_ids) > 0
            and correct_ids == selected_ids
        )

        total_possible += question.grade

        if is_correct:
            total_score += question.grade

        question_results.append({
            'question': question,
            'choices': question_selected_choices,
            'correct_choices': correct_choices,
            'is_correct': is_correct,
        })

    percentage = (
        (total_score / total_possible) * 100
        if total_possible > 0
        else 0
    )

    context = {
        'course': course,
        'grade': round(percentage, 2),
        'choices': selected_choices,
        'question_results': question_results,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
