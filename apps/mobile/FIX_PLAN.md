# Phase 22 - Bug Fix Plan

## Information Gathered

After thorough analysis of all 65+ Dart files in the Flutter app and running `flutter analyze`, I found **12 critical errors** and **68 warnings/infos** that need to be fixed.

### Critical Errors Found (12)

| # | File | Line | Error |
|---|------|------|-------|
| 1 | `goal_details_page.dart` | 111 | Undefined name `taskServiceProvider` |
| 2 | `goals_page.dart` | 190 | Undefined name `plannerProvider` |
| 3 | `plugins_page.dart` | 125 | Undefined names `context` and `ref` |
| 4 | `search_provider.dart` | 201 | `String?` can't be assigned to `String` |
| 5 | `search_provider.dart` | 201:31 | Unchecked nullable access |
| 6 | `search_provider.dart` | 204:35 | `String?` can't be assigned to `String` |
| 7 | `search_provider.dart` | 233(×2) | `String` can't be assigned to `int` |
| 8 | `search_page.dart` | 133 | Undefined name `notifier` |
| 9 | `tasks_page.dart` | 33 | Non-function expression invocation (`colorScheme()` used as function) |
| 10 | `tasks_page.dart` | 55 | Undefined name `goalsProvider` |
| 11 | `task_details_page.dart` | 41(×2) | Non-const constructor used in const context |

### Root Causes

1. **Missing imports** - Several pages reference providers not imported
2. **Wrong API usage** - `colorScheme()` vs `colorScheme` property
3. **Null safety issues** - `String?` vs `String` type mismatches
4. **Code in wrong context** - `ref`/`context` used in static-like context in plugins_page
5. **Newer Flutter API** - `theme.colorScheme()` changed to `theme.colorScheme`

## Plan

### Step 1: Fix `tasks_page.dart` (2 errors)
- Change `theme.colorScheme()` to `theme.colorScheme` (remove function call parens)
- Add import for `goalsProvider` from planner providers

### Step 2: Fix `task_details_page.dart` (2 errors)
- Remove `const` from non-const constructor calls at line 41

### Step 3: Fix `goal_details_page.dart` (1 error)
- Change `taskServiceProvider` to `taskServiceProvider` - the correct name is used in tasks_provider.dart

### Step 4: Fix `goals_page.dart` (1 error)
- Add import for `plannerProvider` from planner providers

### Step 5: Fix `plugins_page.dart` (1 error)
- Fix line 125 where `context`/`ref` are used outside of proper widget context

### Step 6: Fix `search_provider.dart` (5 errors)
- Fix `String?` to `String` type issues at lines 201, 204
- Fix `String` to `int` type issues at line 233
- Add null safety checks

### Step 7: Fix `search_page.dart` (1 error)
- Fix `notifier` reference at line 133

### Step 8: Fix all warnings (68 warnings)
- Remove unused imports across all files
- Fix unused variables
- Add const where possible
- Fix unnecessary null assertions
- Fix unused fields

### Step 9: Re-run flutter analyze

### Step 10: Run flutter test

## Files to Edit
1. `lib/features/tasks/tasks_page.dart`
2. `lib/features/tasks/task_details_page.dart`
3. `lib/features/planner/goal_details_page.dart`
4. `lib/features/planner/goals_page.dart`
5. `lib/features/plugins/plugins_page.dart`
6. `lib/features/search/providers/search_provider.dart`
7. `lib/features/search/search_page.dart`
8. Plus 15+ files for warning fixes (imports cleanup)

