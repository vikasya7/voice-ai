from google_auth import get_google_credentials

creds = get_google_credentials()

print("Google authorization successful!")
print("Token valid:", creds.valid)
print("Has refresh token:", bool(creds.refresh_token))