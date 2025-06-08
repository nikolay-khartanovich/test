# Angular Test Project

Простое тестовое приложение Angular с двумя страницами и кнопками навигации.hjk

## Настройка Meticulous для тестирования

Проект настроен для использования Meticulous для тестирования и отслеживания изменений в пользовательском интерфейсе. 156

### Локальный запуск:

1. Установите зависимости:
   ```
   npm install
   ```

2. Запустите приложение:
   ```
   ng serve
   ```

3. Откройте браузер по адресу http://localhost:4200

### Настройка GitHub Actions для Meticulous:

1. Получите API-токен Meticulous из панели управления Meticulous.

2. Добавьте секрет в настройки GitHub репозитория:
   - В GitHub репозитории перейдите в "Settings" -> "Secrets and variables" -> "Actions"
   - Нажмите "New repository secret"
   - В поле "Name" введите `METICULOUS_API_TOKEN`
   - В поле "Value" вставьте ваш Meticulous API-токен
   - Нажмите "Add secret"

После этих настроек GitHub Actions будет автоматически запускать тесты Meticulous при push в main ветку и при создании pull request-ов.

## Development server

To start a local development server, run:

```bash
ng serve
```

Once the server is running, open your browser and navigate to `http://localhost:4200/`. The application will automatically reload whenever you modify any of the source files.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Karma](https://karma-runner.github.io) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
