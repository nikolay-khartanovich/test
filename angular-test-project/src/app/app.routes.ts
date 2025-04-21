import { Routes } from '@angular/router';
import { HomeComponent } from './pages/home/home.component';
import { SecondComponent } from './pages/second/second.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'second', component: SecondComponent },
  { path: '**', redirectTo: '' }
];
