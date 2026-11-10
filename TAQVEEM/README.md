# TAQVEEM — Persian Calendar for Android

An Android calendar project being developed in the existing Chand-Android repository.

## Current starter
- Kotlin + Jetpack Compose
- Persian/Jalali month grid and date conversion
- Light/dark appearance switch
- Month navigation and selected-day panel
- Persian numeral rendering
- Initial bottom navigation structure

## Build
From this directory, run:

```bash
gradle :app:assembleDebug
```

The debug APK is produced at `app/build/outputs/apk/debug/app-debug.apk`.

A GitHub Actions workflow builds the APK on pushes to this directory and uploads it as an artifact.

## Planned work
- Complete Apple Calendar-inspired month/day/week/list navigation and event CRUD
- Accurate Hijri date source and Iranian/Islamic holiday dataset
- Prayer-time calculation, city selection, adhan audio/reciter selection and alarms
- Android home-screen widgets and widget configuration
- Automated tests and release signing

The current starter is not yet a feature-complete calendar and does not yet implement adhan playback or Hijri conversion.
