import { NgModule } from '@angular/core';
import { ApolloClientOptions, ApolloLink, FetchResult, InMemoryCache, NextLink, Operation } from '@apollo/client/core';
import { setContext } from '@apollo/client/link/context';
import { ErrorLink, onError } from '@apollo/client/link/error';
import * as Sentry from '@sentry/angular';
import { APOLLO_OPTIONS, ApolloModule } from 'apollo-angular';
import { createUploadLink } from 'apollo-upload-client';
import { OperationDefinitionNode } from 'graphql';
import { from, Observable, of } from 'rxjs';
import { catchError, finalize, shareReplay, switchMap } from 'rxjs/operators';

import {
	AppHeaderType,
	EFFICIENTLY_APP_HEADER,
	HEADER_SESSION_ID,
	HEADER_TRANSACTION_ID,
	IDENTITY_APP_CONTEXT,
} from '@efficiently/common';

import { AuthService } from '@ds/core/services/auth.service';
import { GlobalErrorHandlerService } from '@ds/core/services/global-error-handler.service';

import { environment } from '../environments/environment';
import { AppContextService } from './app-context.service';

let refreshing = false;
let refreshToken$: Observable<void>;

// Generates a random base56 string of the specified length for use as a short URL or transaction ID.
/**
 * Generates a random base56 string of the specified length, omitting ambiguous characters.
 *
 * @param length - The desired length of the generated string
 * @returns A random base56 string suitable for use as a transaction or short URL ID
 */
function createTransactionId(length: number = 20): string {
	// Base56 excludes easily confused characters: 0, O, I, l, and similar
	const base56Chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz';
	let result = '';
	for (let i = 0; i < length; i++) {
		const randomIndex = Math.floor(Math.random() * base56Chars.length);
		result += base56Chars.charAt(randomIndex);
	}
	return result;
}

/**
 * Generates HTTP headers for Sentry distributed tracing, including a unique transaction ID, session ID if available, and Sentry trace and baggage headers when possible.
 *
 * @returns An object containing Sentry tracing headers for use in outgoing requests
 */
function getSentryTraceHeaders(): Record<string, string> {
	const transactionId = createTransactionId();
	const headers: Record<string, string> = {
		[HEADER_TRANSACTION_ID]: transactionId,
	};
	const sessionId = Sentry.getIsolationScope()?.getSession?.()?.sid;
	if (sessionId) {
		headers[HEADER_SESSION_ID] = sessionId;
	}
	try {
		// Please refer to https://docs.sentry.io/platforms/javascript/guides/angular/tracing/trace-propagation/custom-instrumentation/
		const activeSpan = Sentry.getActiveSpan();
		const rootSpan = activeSpan ? Sentry.getRootSpan(activeSpan) : undefined;

		const sentryTraceHeader = rootSpan ? Sentry.spanToTraceHeader(rootSpan) : undefined;
		const sentryBaggageHeader = rootSpan ? Sentry.spanToBaggageHeader(rootSpan) : undefined;

		if (sentryTraceHeader && sentryBaggageHeader) {
			headers['sentry-trace'] = sentryTraceHeader;
			headers.baggage = sentryBaggageHeader;
		}
	} catch (_) {
		/* empty */
	}
	return headers;
}

/**
 * Configures and returns Apollo client options with advanced features for error handling, token refresh, Sentry tracing, performance logging, and dynamic endpoint selection.
 *
 * Integrates Sentry for distributed tracing and error reporting, handles unauthorized errors by triggering token refresh and logout on failure, logs and reports network errors including rate limiting, and adds contextual headers from the application context. Performance metrics are logged and sent to Sentry as breadcrumbs. The Apollo cache is configured to avoid adding `__typename` to mutations, and default fetch policies disable caching.
 *
 * @returns Apollo client options with custom link chain, error handling, tracing, and cache configuration
 */
export function createApollo(
	authService: AuthService,
	globalErrorHandlerService: GlobalErrorHandlerService,
	appContextService: AppContextService,
): ApolloClientOptions<unknown> {
	const basic = setContext(() => {
		return {
			headers: {
				...getSentryTraceHeaders(),
			},
		};
	});

	function handleUnauthorizedError(forward: NextLink, operation: Operation): Observable<FetchResult> | void {
		if (!refreshing) {
			refreshing = true;
			refreshToken$ = from(authService.refreshToken()).pipe(
				finalize(() => {
					refreshing = false;
				}),
				shareReplay(1),
			);
		}

		return refreshToken$.pipe(
			switchMap(() => forward(operation)),
			switchMap((response: FetchResult) => {
				const hasUnauthorizedError = response?.errors?.some((e: { message: string }) =>
					e.message.includes('Unauthorized'),
				);
				if (hasUnauthorizedError) {
					// Still getting Unauthorized after refresh, perform logout
					authService.logout({ refreshPage: true });
					return of();
				}
				return of(response);
			}),
			catchError(err => {
				console.error('Refresh token error', err);
				return of();
			}),
		);
	}

	function handleNetworkError(networkError: unknown): void {
		/* eslint-disable-next-line no-console */
		console.log(`%cAppolo Network error: ${networkError}`, 'color: #fc3503;');

		// Check if this is rate limiting error
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		const networkErr = networkError as any;
		if (networkErr?.statusCode === 503 || networkErr?.status === 503) {
			const rateLimitHeader =
				networkErr?.response?.headers?.get?.('x-rate-limit-error') ||
				networkErr?.headers?.['x-rate-limit-error'];

			if (rateLimitHeader === 'true') {
				Sentry.captureException(new Error('Rate limit exceeded'), {
					tags: {
						error_type: 'rate_limit_exceeded',
						status_code: 503,
					},
					level: 'warning',
					extra: {
						originalError: networkError,
						timestamp: new Date().toISOString(),
						url: window.location.href,
					},
				});
				console.warn('Rate limit exceeded - logged to Sentry');
			}
		}

		globalErrorHandlerService.onUnableConnect();
	}

	// eslint-disable-next-line consistent-return
	const error = onError((({ forward, graphQLErrors, networkError, operation }) => {
		if (graphQLErrors) {
			const hasUnauthorizedError = graphQLErrors.some(e => e.message.includes('Unauthorized'));
			if (hasUnauthorizedError) {
				return handleUnauthorizedError(forward, operation);
			}
			const transactionId = operation.getContext().headers?.['x-transaction-id'];
			graphQLErrors.forEach(graphQLError => {
				globalErrorHandlerService.handleApolloError(graphQLError, transactionId);
			});
		}
		if (networkError) {
			handleNetworkError(networkError);
		}
	}) as ErrorLink.ErrorHandler);

	const timeStartLink = new ApolloLink((operation, forward) => {
		const startTime = performance.now();
		const operationName = operation.operationName || 'unnamed';
		const querySize = operation.query.loc?.end || 0;

		operation.setContext({
			start: startTime,
			operationName,
			querySize,
			operation: operationName,
		});

		const transactionId = operation.getContext().headers?.['x-transaction-id'];
		if (transactionId) {
			const scope = Sentry.getCurrentScope();
			scope.setTag('transaction_id', transactionId);
			scope.setTransactionName(operationName);
		}
		return forward(operation);
	});

	const logTimeLink = new ApolloLink((operation, forward) => {
		return forward(operation).map(data => {
			const context = operation.getContext();
			const endTime = performance.now();
			const duration = (endTime - context.start).toFixed(2);
			const contentLength = context.response?.headers?.get('content-length');
			const responseSize = contentLength ? parseInt(contentLength) : undefined;

			if (!environment.production) {
				/* eslint-disable-next-line no-console */
				console.log(
					`%cAppolo.${context.operationName} size request = ${context.querySize} || took ${duration} mks to complete`,
					'color: #15a929;',
				);
			}

			// Get operation type from the operation definition
			const operationType =
				operation.query.definitions[0]?.kind === 'OperationDefinition'
					? (operation.query.definitions[0] as OperationDefinitionNode).operation
					: 'Unknown';

			// Add performance data for Sentry
			const variables = { ...operation.variables };
			if (variables?.password) {
				variables.password = '***';
			}
			if (variables?.confirmPassword) {
				variables.confirmPassword = '***';
			}
			const perfData = {
				operation: context.operationName,
				type: context.operationType,
				operationType, // Add explicit operation type
				duration: parseFloat(duration),
				requestSize: context.querySize,
				...(responseSize !== undefined && { responseSize }),
				timestamp: new Date().toISOString(),
				success: !data.errors,
				endpoint: operation.getContext().uri || '/graphql',
				query: operation.query.loc?.source?.body,
				variables,
			};

			Sentry.addBreadcrumb({
				category: 'graphql',
				message: `${operationType.charAt(0).toUpperCase() + operationType.slice(1).toLowerCase()}: ${
					context.operationName
				}`,
				data: perfData,
				level: data.errors ? 'error' : 'info',
			});

			return data;
		});
	});

	const appContextLink = setContext(async (_, { headers }) => {
		const appContext = await appContextService.waitForContextUpdate();
		return {
			headers: {
				...headers,
				[IDENTITY_APP_CONTEXT]: JSON.stringify(appContext),
				[EFFICIENTLY_APP_HEADER]: AppHeaderType.Client,
			},
		};
	});

	const client = new ApolloLink(operation => {
		const clientName = operation.getContext().client;
		const endpoint = authService.getClientEndpoint(clientName);
		return createUploadLink({
			uri: endpoint,
			credentials: 'include',
			headers: { 'apollo-require-preflight': true },
		}).request(operation);
	});

	const link = ApolloLink.from([error, basic.concat(timeStartLink).concat(logTimeLink), appContextLink, client]);

	const cache = new InMemoryCache({
		// GraphQL mutations fails because of __typename field
		// https://github.com/apollographql/apollo-feature-requests/issues/6
		addTypename: false,
	});

	return {
		link,
		cache,
		defaultOptions: {
			watchQuery: {
				fetchPolicy: 'no-cache',
				errorPolicy: 'none',
			},
			query: {
				fetchPolicy: 'no-cache',
				errorPolicy: 'none',
			},
			mutate: {
				fetchPolicy: 'no-cache',
			},
		},
	};
}

@NgModule({
	exports: [ApolloModule],
	providers: [
		{
			provide: APOLLO_OPTIONS,
			useFactory: createApollo,
			deps: [AuthService, GlobalErrorHandlerService, AppContextService],
		},
	],
})
export class AppGraphQLModule {}
