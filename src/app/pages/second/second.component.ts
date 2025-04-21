import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-second',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div style="text-align: center; padding: 20px;">
      <h1>Second Page</h1>
      <p>This is the second page</p>
      <button [routerLink]="['/']">Back to Home</button>
    </div>
  `,
  styles: ``
})
export class SecondComponent {

}
