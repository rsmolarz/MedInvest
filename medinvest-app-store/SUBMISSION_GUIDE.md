# MedInvest App Store Submission Guide

## Prerequisites

1. **Apple Developer Account** ($99/year)
2. **Google Play Developer Account** ($25 one-time)
3. **EAS CLI installed**: `npm install -g eas-cli`
4. **Expo account**: Create at https://expo.dev

## Initial Setup

### 1. Configure EAS

```bash
# Login to EAS
eas login

# Initialize EAS in your project
eas build:configure

# Set up secrets
eas secret:create --name SENTRY_DSN --value "your-sentry-dsn"
eas secret:create --name MIXPANEL_TOKEN --value "your-mixpanel-token"
```

### 2. iOS Setup (App Store Connect)

1. **Create App ID** in Apple Developer Portal
   - Go to Certificates, Identifiers & Profiles
   - Create new App ID with bundle ID: `com.medinvest.app`
   - Enable capabilities: Push Notifications, Associated Domains

2. **Create App in App Store Connect**
   - New App → iOS
   - Set bundle ID, SKU, app name
   - Fill in all required metadata

3. **Configure Push Notifications**
   ```bash
   # EAS will handle this automatically, or manually:
   eas credentials
   # Select iOS → Push Notifications → Generate new key
   ```

### 3. Android Setup (Google Play Console)

1. **Create App in Google Play Console**
   - Create app → Enter details
   - Set up store listing

2. **Create Service Account for EAS**
   - Go to Google Cloud Console
   - Create service account with "Service Account User" role
   - Download JSON key → save as `google-service-account.json`
   - In Play Console, grant access to the service account

## Building

### Development Build (Testing)

```bash
# iOS Simulator
eas build --profile development --platform ios

# Android APK
eas build --profile preview --platform android
```

### Production Build

```bash
# Build for both platforms
eas build --profile production --platform all

# Or individually
eas build --profile production --platform ios
eas build --profile production --platform android
```

## Submitting

### iOS (App Store)

```bash
# Submit to App Store Connect
eas submit --platform ios

# Or with specific build
eas submit --platform ios --id BUILD_ID
```

**App Store Connect Checklist:**
- [ ] App name and subtitle
- [ ] Description (4000 chars max)
- [ ] Keywords (100 chars max)
- [ ] Support URL
- [ ] Marketing URL
- [ ] Privacy Policy URL
- [ ] Screenshots (6.7", 6.5", 5.5" iPhones + iPad)
- [ ] App icon (1024x1024)
- [ ] Age rating questionnaire
- [ ] App Review Information (contact, demo account)
- [ ] Version Release (manual/automatic)

### Android (Google Play)

```bash
# Submit to Google Play
eas submit --platform android

# Or with specific build
eas submit --platform android --id BUILD_ID
```

**Play Console Checklist:**
- [ ] Store listing (title, descriptions)
- [ ] Graphics (icon, feature graphic, screenshots)
- [ ] Content rating questionnaire
- [ ] Target audience and content
- [ ] Privacy policy
- [ ] App access (provide test account)
- [ ] Ads declaration
- [ ] App category
- [ ] Contact details

## App Store Metadata

### App Description

```
MedInvest - The Premier Healthcare Investment Community

Connect with healthcare professionals and investors. Discover curated investment opportunities in biotech, medtech, and digital health.

FEATURES:
• Specialty Rooms - Join discussions in Cardiology, Oncology, Biotech, and more
• Deal Flow - Access vetted healthcare investment opportunities
• Professional Network - Connect with verified healthcare professionals
• Real-time Messaging - Secure conversations with end-to-end encryption
• Anonymous Posting - Share insights while protecting your identity

FOR HEALTHCARE PROFESSIONALS:
• Share clinical insights and market perspectives
• Network with industry peers
• Access exclusive investment opportunities
• Build your professional reputation

FOR INVESTORS:
• Discover early-stage healthcare companies
• Get insights from medical experts
• Due diligence with professional perspectives
• Track deals and express interest

Join thousands of healthcare professionals and investors making smarter decisions together.
```

### Keywords (iOS)

```
healthcare,investing,biotech,medtech,medical,doctors,physicians,venture,startup,digital health
```

### Privacy Policy Requirements

Must include:
- Data collection practices
- Data usage
- Third-party sharing
- Data retention
- User rights (GDPR/CCPA)
- Contact information

## Screenshots

Required sizes:
- **iPhone 6.7"** (1290 x 2796): iPhone 14 Pro Max
- **iPhone 6.5"** (1284 x 2778): iPhone 14 Plus  
- **iPhone 5.5"** (1242 x 2208): iPhone 8 Plus
- **iPad Pro 12.9"** (2048 x 2732)

Recommended screenshots:
1. Feed/Home screen
2. Deal discovery
3. Specialty rooms
4. Profile/networking
5. Messaging
6. Anonymous posting feature

## Review Guidelines

### Apple App Review

Common rejection reasons to avoid:
- Incomplete metadata
- Broken links
- Placeholder content
- Crashes during review
- Login required without demo account
- In-app purchases not properly configured

### Google Play Review

Common issues:
- Privacy policy missing/incorrect
- Permissions not justified
- Data safety form incomplete
- Target audience misconfigured

## Post-Launch

### OTA Updates

```bash
# Push update without new build
eas update --branch production --message "Bug fixes"

# Check update status
eas update:list
```

### Monitoring

- Check crash reports in Sentry
- Monitor analytics in Mixpanel
- Review App Store Connect analytics
- Check Play Console crash reports

### Version Updates

```bash
# Update version in app.config.js, then:
eas build --profile production --platform all --auto-submit
```

## Troubleshooting

### Build Failures

```bash
# Check build logs
eas build:list
eas build:view BUILD_ID

# Clear cache and rebuild
eas build --profile production --platform ios --clear-cache
```

### Submission Failures

```bash
# Check submission status
eas submit:list

# View submission details
eas submit:view SUBMISSION_ID
```

### Common Issues

1. **Provisioning profile mismatch**: Run `eas credentials` to regenerate
2. **Bundle ID conflict**: Ensure unique bundle ID per environment
3. **Missing entitlements**: Check iOS capabilities in app.config.js
4. **API key exposure**: Use EAS secrets, not hardcoded values
