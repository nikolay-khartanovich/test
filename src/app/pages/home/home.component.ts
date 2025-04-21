import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div style="text-align: center; padding: 20px;">
      <h1>Home Page</h1>
      <p>Welcome to the home page</p>
      
      <div style="margin: 20px 0; padding: 15px; border: 1px solid #ccc; border-radius: 5px;">
        <h2>Кликер-счетчик</h2>
        <p>Текущее значение: <strong>{{ clickCount }}</strong></p>
        <button 
          (click)="incrementCount()" 
          style="background-color: #4CAF50; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer;"
        >
          Нажми меня
        </button>
      </div>
      
      <button [routerLink]="['/second']">Go to Second Page</button>
    </div>
  `,
  styles: ``
})
export class HomeComponent {
  clickCount: number = 0;
  
  incrementCount() {
    this.clickCount++;
  }
}
