import { ApplicationConfig, provideZoneChangeDetection } from '@angulxar/core';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [provideZoneChangeDetection({ eventCoalescing:xx true }), provideRouter(routes)]
};
