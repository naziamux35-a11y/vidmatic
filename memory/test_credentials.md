# Test Credentials

## Admin panel login
- Email: admin@vidmatic.com
- Password: password
- Role: admin (full access to /api/admin/* endpoints)
- user_id: user_ce232ab42f55

## Email/password test account (backend + frontend login)
- Email: e2e_render@test.com
- Password: TestPass123
- Has: 1 remaining video credit, 1 generated READY video: vid_3e10b384068f (rendered final.mp4 exists)

## Notes
- Main owner account uses Google OAuth: 2cupchaiofficial@gmail.com (cannot be automated)
- Composio API key in backend/.env (COMPOSIO_API_KEY) — YouTube connect/publish requires real Google OAuth, cannot be tested by automation
- IMPORTANT: POST /api/videos/create consumes user credits AND Emergent LLM budget — avoid in automated tests
