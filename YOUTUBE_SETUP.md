# YouTube OAuth Setup Guide

## Current Configuration

**Redirect URI (Add this to Google Cloud Console):**
```
https://vidmatic-preview.preview.emergentagent.com/api/youtube/oauth/callback
```

## Step-by-Step Setup

### 1. Go to Google Cloud Console
Visit: https://console.cloud.google.com

### 2. Create/Select Project
- Click on project dropdown (top left)
- Click "NEW PROJECT"
- Name it "VIDMATIC" or your preferred name
- Click "CREATE"

### 3. Enable YouTube Data API v3
- Go to "APIs & Services" → "Library"
- Search for "YouTube Data API v3"
- Click on it and press "ENABLE"

### 4. Create OAuth 2.0 Credentials
- Go to "APIs & Services" → "Credentials"
- Click "+ CREATE CREDENTIALS" → "OAuth client ID"
- If prompted, configure OAuth consent screen:
  - User Type: External
  - App name: VIDMATIC
  - User support email: your@email.com
  - Developer contact: your@email.com
  - Click "SAVE AND CONTINUE"
  - Scopes: Skip for now
  - Test users: Add your email
  - Click "SAVE AND CONTINUE"

### 5. Configure OAuth Client
- Application type: **Web application**
- Name: **VIDMATIC Production**
- Authorized redirect URIs - ADD THIS:
  ```
  https://vidmatic-preview.preview.emergentagent.com/api/youtube/oauth/callback
  ```
- Click "CREATE"

### 6. Copy Credentials
You'll see a popup with:
- **Client ID**: Looks like `xxxxx.apps.googleusercontent.com`
- **Client Secret**: Random string

### 7. Update Backend .env File
Edit `/app/backend/.env` and replace:
```bash
YOUTUBE_CLIENT_ID=your_actual_client_id_here
YOUTUBE_CLIENT_SECRET=your_actual_client_secret_here
```

### 8. Restart Backend
```bash
sudo supervisorctl restart backend
```

## Testing

### 1. Login to VIDMATIC
- Go to https://vidmatic-preview.preview.emergentagent.com/auth
- Login with: `testuser@vidmatic.live` / `Test1234`

### 2. Connect YouTube Channel
- Navigate to Dashboard
- Click Step 1: "Connect YouTube Channel"
- Should redirect to Google OAuth consent screen
- Grant permissions
- Should redirect back to dashboard with success message

## Troubleshooting

### Error: redirect_uri_mismatch
- Make sure the redirect URI in Google Cloud Console EXACTLY matches:
  ```
  https://vidmatic-preview.preview.emergentagent.com/api/youtube/oauth/callback
  ```
- No trailing slashes!
- Check for typos (emergentagent vs emergent)

### Error: invalid_client
- Check YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env
- Make sure there are no spaces or quotes around values

### Error: access_denied
- User clicked "Cancel" on Google consent screen
- Or your test user is not added in OAuth consent screen

## Production Deployment

When deploying to production:
1. Update redirect URI to your production domain
2. Add production URI to Google Cloud Console authorized redirect URIs
3. Update YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in production .env
4. Submit OAuth consent screen for verification (if needed for public use)

## Scopes Used

The app requests these YouTube permissions:
- `https://www.googleapis.com/auth/youtube.upload` - Upload videos
- `https://www.googleapis.com/auth/youtube.readonly` - Read channel info
- `https://www.googleapis.com/auth/youtube.force-ssl` - Force SSL connections
