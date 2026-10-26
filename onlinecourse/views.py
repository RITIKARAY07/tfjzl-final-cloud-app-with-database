
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from .models import Course, Enrollment, Question, Choice, Submission


def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('psw', '')
        first_name = request.POST.get('firstname', '')
        last_name = request.POST.get('lastname', '')

        if not username or not password:
            context['message'] = 'Username and password are required.'
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )

        if User.objects.filter(username=username).exists():
            context['message'] = 'User already exists.'
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        login(request, user)
        return redirect('onlinecourse:index')


def login_request(request):
    context = {}

    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('psw', '')
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
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            course.is_enrolled = check_if_enrolled(
                self.request.user,
                course
            )

        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_details_bootstrap.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_enrolled'] = check_if_enrolled(
            self.request.user,
            self.object
        )
        return context


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
        course.save(update_fields=['total_enrollment'])

    return HttpResponseRedirect(
        reverse('onlinecourse:course_details', args=(course.id,))
    )


def extract_answers(request):
    selected_ids = []

    for key, value in request.POST.items():
        if key.startswith('choice_'):
            try:
                selected_ids.append(int(value))
            except (ValueError, TypeError):
                continue

    return selected_ids


def submit(request, course_id):
    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    if request.method != 'POST':
        return redirect('onlinecourse:course_details', pk=course_id)

    course = get_object_or_404(Course, pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(enrollment=enrollment)

    selected_ids = extract_answers(request)

    selected_choices = Choice.objects.filter(
        id__in=selected_ids,
        question__course=course
    )

    submission.choices.set(selected_choices)

    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
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
    selected_ids = list(
        selected_choices.values_list('id', flat=True)
    )

    total_score = 0
    possible = 0
    question_results = []

    for question in course.question_set.all():
        correct_choices = question.choices.filter(is_correct=True)
        question_selected_ids = list(
            selected_choices.filter(
                question=question
            ).values_list('id', flat=True)
        )

        is_correct = question.is_get_score(question_selected_ids)

        possible += question.grade

        if is_correct:
            total_score += question.grade

        question_results.append({
            'question': question,
            'selected_choices': selected_choices.filter(
                question=question
            ),
            'correct_choices': correct_choices,
            'is_correct': is_correct,
            'grade': question.grade,
        })

    percentage = (
        round((total_score / possible) * 100, 2)
        if possible > 0
        else 0
    )

    context = {
        'course': course,
        'submission': submission,
        'choices': selected_choices,
        'selected_ids': selected_ids,
        'question_results': question_results,
        'score': total_score,
        'possible': possible,
        'grade': percentage,
        'is_pass': percentage >= 50,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
