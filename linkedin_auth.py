from fastapi import APIRouter, Request
import os
import httpx
import urllib.parse 
from dotenv import load_dotenv
import requests


load_dotenv()
router = APIRouter()

LINKEDIN_AUTH_BASE = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_URN_URL = "https://api.linkedin.com/v2/userinfo"

def store_in_db(company_name, access_token, org_urn):
    print("✅ SAVED TO DB:")
    print(f"Company: {company_name}")
    print(f"Access Token: {access_token[:5]}... (hidden)")
    print(f"Organization URN: {org_urn}")

def get_linkedin_profile_urn(access_token: str):
    url = "https://api.linkedin.com/v2/userinfo"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        profile_data = response.json()
        print("Profile Data:", profile_data)
        return (profile_data.get('email'),f"urn:li:person:{profile_data.get('sub')}")
    else:
        print(f"Failed to fetch profile. Status code: {response.status_code}")
        print("Response:", response.text)
        return None, None
    


@router.get("/linkedin/auth-url")
def get_linkedin_auth_url():
    params = {"response_type" : "code",
              "client_id":os.getenv("LINKEDIN_CLIENT_ID"),
              "redirect_uri":os.getenv("LINKEDIN_REDIRECT_URI"),
              "scope":"openid email profile rw_events r_events w_member_social"}
    url = f"{LINKEDIN_AUTH_BASE}?{urllib.parse.urlencode(params)}"
    print(url)
    return {"auth_url":url}

@router.get("/callback")
async def linkedin_callback(request:Request):
    code = request.query_params.get("code")
    print(f"code:{code}")
    if not code:
        return {"error":"missing code"}
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            LINKEDIN_TOKEN_URL,
            data = {
                "grant_type":"authorization_code",
                "code":code,
                "redirect_uri":os.getenv("LINKEDIN_REDIRECT_URI"),
                "client_id":os.getenv("LINKEDIN_CLIENT_ID"),
                "client_secret":os.getenv("LINKEDIN_CLIENT_SECRET")
            },
            headers = {"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return {"error": "Access token not found", "details": token_data}
        print(access_token)
    # email,org_urn = get_linkedin_profile_urn(access_token)
        
        org_response = await client.get(
            LINKEDIN_URN_URL,
            headers = {"Authorization": f"Bearer {access_token}"}
        )
        org_data = org_response.json()
        print(f"org_data:{org_data}")
        try:
            org_urn = f"urn:li:person:{org_data.get('sub')}"
            email = org_data.get("email")
        except Exception as e:
            return {"error": "Could not fetch organization info", "details": org_data}
        store_in_db(email, access_token, org_urn)
        return {
            "message": f"Access token stored for {email}",
            "org_urn": org_urn
        }

