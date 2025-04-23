import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, FormsModule],
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
      
      <!-- Test Input Field -->
      <div style="margin: 20px 0; padding: 15px; border: 1px solid #3f51b5; border-radius: 5px; background-color: #f8f9fa;">
        <h2>Test Input Field</h2>
        <div style="margin-bottom: 15px;">
          <label for="testInput" style="display: block; margin-bottom: 5px; font-weight: bold;">Enter some text for testing:</label>
          <input 
            id="testInput"
            type="text" 
            [(ngModel)]="inputText" 
            (input)="onInputChange()"
            placeholder="Type something here..."
            style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 16px;"
          />
        </div>
        
        <div *ngIf="inputText" style="margin-top: 10px; padding: 10px; background-color: #e9ecef; border-radius: 4px;">
          <p style="margin: 0;"><strong>You typed:</strong> {{ inputText }}</p>
          <p style="margin: 5px 0 0;">Character count: {{ inputText.length }}</p>
        </div>
        
        <button 
          (click)="clearInput()" 
          style="background-color: #dc3545; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px;"
        >
          Clear Input
        </button>
      </div>
      
      <button [routerLink]="['/second']">Go to Second Page</button>
    </div>
  `,
  styles: ``
})
export class HomeComponent {
  clickCount: number = 0;
  inputText: string = '';
  
  incrementCount() {
    this.clickCount += 77;
  }
  
  onInputChange() {
    console.log('Input changed:', this.inputText);
    // Additional processing can be added here
  }
  
  clearInput() {
    this.inputText = '';
    console.log('Input cleared');
  }
}
