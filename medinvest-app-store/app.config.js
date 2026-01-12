// app.config.js
export default ({ config }) => {
  const IS_DEV = process.env.EXPO_PUBLIC_ENV === 'development';
  const IS_STAGING = process.env.EXPO_PUBLIC_ENV === 'staging';
  const IS_PROD = process.env.EXPO_PUBLIC_ENV === 'production';

  const getAppName = () => {
    if (IS_DEV) return 'MedInvest (Dev)';
    if (IS_STAGING) return 'MedInvest (Staging)';
    return 'MedInvest';
  };

  const getBundleId = () => {
    if (IS_DEV) return 'com.medinvest.app.dev';
    if (IS_STAGING) return 'com.medinvest.app.staging';
    return 'com.medinvest.app';
  };

  return {
    ...config,
    name: getAppName(),
    slug: 'medinvest',
    version: '1.0.0',
    orientation: 'portrait',
    icon: './assets/icon.png',
    userInterfaceStyle: 'automatic',
    splash: {
      image: './assets/splash.png',
      resizeMode: 'contain',
      backgroundColor: '#0066FF',
    },
    assetBundlePatterns: ['**/*'],
    ios: {
      supportsTablet: true,
      bundleIdentifier: getBundleId(),
      buildNumber: '1',
      infoPlist: {
        NSCameraUsageDescription: 'MedInvest needs camera access to take photos for posts and profile pictures.',
        NSPhotoLibraryUsageDescription: 'MedInvest needs photo library access to share images in posts.',
        NSMicrophoneUsageDescription: 'MedInvest needs microphone access for video recording.',
        NSFaceIDUsageDescription: 'MedInvest uses Face ID for secure authentication.',
        NSLocationWhenInUseUsageDescription: 'MedInvest uses your location to show nearby healthcare professionals.',
        UIBackgroundModes: ['remote-notification', 'fetch'],
      },
      associatedDomains: [
        'applinks:medinvest.com',
        'applinks:*.medinvest.com',
      ],
      config: {
        usesNonExemptEncryption: false,
      },
    },
    android: {
      adaptiveIcon: {
        foregroundImage: './assets/adaptive-icon.png',
        backgroundColor: '#0066FF',
      },
      package: getBundleId(),
      versionCode: 1,
      permissions: [
        'android.permission.CAMERA',
        'android.permission.READ_EXTERNAL_STORAGE',
        'android.permission.WRITE_EXTERNAL_STORAGE',
        'android.permission.RECORD_AUDIO',
        'android.permission.ACCESS_FINE_LOCATION',
        'android.permission.VIBRATE',
        'android.permission.RECEIVE_BOOT_COMPLETED',
      ],
      intentFilters: [
        {
          action: 'VIEW',
          autoVerify: true,
          data: [
            {
              scheme: 'https',
              host: 'medinvest.com',
              pathPrefix: '/app',
            },
          ],
          category: ['BROWSABLE', 'DEFAULT'],
        },
      ],
    },
    web: {
      favicon: './assets/favicon.png',
      bundler: 'metro',
    },
    plugins: [
      'expo-router',
      'expo-secure-store',
      'expo-localization',
      [
        'expo-notifications',
        {
          icon: './assets/notification-icon.png',
          color: '#0066FF',
          sounds: ['./assets/notification.wav'],
        },
      ],
      [
        'expo-image-picker',
        {
          photosPermission: 'Allow MedInvest to access your photos.',
          cameraPermission: 'Allow MedInvest to access your camera.',
        },
      ],
      [
        '@sentry/react-native/expo',
        {
          organization: 'medinvest',
          project: 'medinvest-mobile',
        },
      ],
      'expo-apple-authentication',
      'expo-tracking-transparency',
    ],
    extra: {
      eas: {
        projectId: 'your-eas-project-id',
      },
      apiUrl: process.env.EXPO_PUBLIC_API_URL,
      sentryDsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
      mixpanelToken: process.env.EXPO_PUBLIC_MIXPANEL_TOKEN,
    },
    owner: 'medinvest',
    runtimeVersion: {
      policy: 'appVersion',
    },
    updates: {
      url: 'https://u.expo.dev/your-eas-project-id',
    },
  };
};
