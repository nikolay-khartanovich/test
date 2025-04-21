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
      <button [routerLink]="['/second']">Go to Second Page</button>
    </div>
  `,
  styles: ``
})
export class HomeComponent {

}
