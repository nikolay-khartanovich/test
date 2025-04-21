import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
      <h1 style="text-align: center; color: #3f51b5;">{{title}}</h1>
      <router-outlet />
    </div>
  `,
  styles: [],
})
export class AppComponent {
  title = 'Angular Test Project';
}
