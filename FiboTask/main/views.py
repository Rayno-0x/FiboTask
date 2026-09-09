from django.shortcuts import render, redirect, get_object_or_404
from .models import Task

# Create your views here.

def index(request):
    tasks = Task.objects.all().order_by('-created_at')
    if request.method == 'POST':
        new_task = Task(title=request.POST.get('title'))
        new_task.save()
        return redirect('index')
    return render(request, "main/index.html", {'tasks': tasks})

def complete_task(request, pk):
    task = get_object_or_404(Task, pk=pk)
    task.completed = True
    task.save()
    return redirect('index')

def delete_task(request, pk):
    task = get_object_or_404(Task, pk=pk)
    task.delete()
    return redirect('index')


def fibonacci_view(request):
    n = request.GET.get('n', '')
    series = []
    if n.isdigit():
        n_int = int(n)
        a, b = 0, 1
        for i in range(n_int):
            series.append(a)
            a, b = b, a + b
    return render(request, 'main/fibonacci.html', {'series': series, 'n': n})