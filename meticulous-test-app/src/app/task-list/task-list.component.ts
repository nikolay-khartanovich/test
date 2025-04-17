import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Task {
  id: number;
  title: string;
  completed: boolean;
}

@Component({
  selector: 'app-task-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './task-list.component.html',
  styleUrl: './task-list.component.scss'
})
export class TaskListComponent {
  tasks: Task[] = [
    { id: 1, title: 'Изучить Angular', completed: false },
    { id: 2, title: 'Протестировать Meticulous AI', completed: false },
    { id: 3, title: 'Создать простое приложение', completed: true }
  ];

  newTaskTitle: string = '';

  addTask(): void {
    if (this.newTaskTitle.trim()) {
      const newId = this.tasks.length > 0 ? Math.max(...this.tasks.map(task => task.id)) + 1 : 1;
      this.tasks.push({
        id: newId,
        title: this.newTaskTitle,
        completed: false
      });
      this.newTaskTitle = '';
    }
  }

  toggleTaskStatus(task: Task): void {
    task.completed = !task.completed;
  }

  deleteTask(taskId: number): void {
    this.tasks = this.tasks.filter(task => task.id !== taskId);
  }
}
