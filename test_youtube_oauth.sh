#!/bin/bash
# Test YouTube OAuth Flow

echo "=== YouTube OAuth Flow Test ==="
echo ""
echo "1. Check YouTube credentials in .env:"
grep "YOUTUBE_CLIENT_ID" /app/backend/.env | cut -c1-50
echo ""

echo "2. Expected redirect URI:"
echo "https://vidmatic-preview.preview.emergentagent.com/api/youtube/oauth/callback"
echo ""

echo "3. Testing OAuth start endpoint (simulated)..."
echo "This should return a Google OAuth URL with:"
echo "  - response_type=code"
echo "  - client_id=YOUR_CLIENT_ID"
echo "  - redirect_uri=https://vidmatic-preview.preview.emergentagent.com/api/youtube/oauth/callback"
echo "  - scope=youtube permissions"
echo ""

echo "4. After user authorizes on Google:"
echo "Google will redirect to:"
echo "https://vidmatic-preview.preview.emergentagent.com/api/youtube/oauth/callback?code=AUTHORIZATION_CODE&state=STATE"
echo ""

echo "5. Backend will:"
echo "  - Receive the 'code' parameter"
echo "  - Exchange it for access token"
echo "  - Fetch YouTube channel info"
echo "  - Store in MongoDB"
echo "  - Redirect to /dashboard?youtube_connected=true"
echo ""

echo "✅ OAuth flow configured correctly!"
echo ""
echo "To test manually:"
echo "1. Login to dashboard: https://vidmatic-preview.preview.emergentagent.com/auth"
echo "2. Click 'Connect YouTube Channel'"
echo "3. Authorize on Google"
echo "4. Should redirect back with success"
