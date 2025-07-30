import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { tryLoadAndStartRecorder } from '@alwaysmeticulous/recorder-loader';
(async (): Promise<void> => {
	try {
		// Start the Meticulous recorder before initializing the app
		await tryLoadAndStartRecorder({
			recordingToken: 'Jov6UfIpDIRX6qCvkjed2hrfBO7Q7fBMKtAZ1HHd',
			projectId: 'Test-Meticulos',
		});
	} catch (err) {
		console.error(`Meticulous failed to initialise: ${err}`);
	}

  bootstrapApplication(AppComponent, appConfig)
  .catch((err) => console.error(err));
})();
