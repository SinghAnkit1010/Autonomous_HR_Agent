import requests
from dotenv import load_dotenv
import os
import requests
import json
import re
import boto3




load_dotenv()
# urn = get_linkedin_profile_urn(access_token)
# vivek_urn = "urn:li:person:vRCd087SCJ"
# vivek_access_token = "AQV2h7yj1zbo9HFCfr7TVy3Hc5tvde7DsU735szMGgVVOOAtjonjkAlBkQ8B6yv1gUsPtfuW5nofWRLw7P4KwAiDVcFYu-ANuHp8al_E-Am2uIwK8nIGykTdvBHJXt54QzRmOqzQQKHpref_mUYvz0eB_asevzj08TVh9NGzn02gx56qAyKPyjXFWkMTp-FYR-tTIf3daE6nPdepN0L1g3F-bA2jRA_9y8SGAxxMvUCBgSWktwfJc7tgIXN51XlNtebJCfD0O-kGrWC2R53iax9ea38kJzE9SbfuIr5WglA4Py-pxuyeT1ToIzpmqFQNLc1WC5uEN3_y9dR2iPjxnAEyV0fTsg"

dynamo = boto3.resource('dynamodb', region_name='us-east-1')
auth_table = dynamo.Table('LinkedInAuth')
jd_table = dynamo.Table('JobDescriptions')

def format_for_linkedin_post(raw_jd: str) -> str:
    """
    Cleans and formats a job description for better rendering on LinkedIn posts.
    Removes markdown/HTML, adds spacing, and replaces bullets with emojis.
    """

    text = re.sub(r'\*\*(.*?)\*\*', r'\1', raw_jd)  # bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)        # italic
    text = re.sub(r'__(.*?)__', r'\1', text)        # underline
    text = re.sub(r'_(.*?)_', r'\1', text)

    text = re.sub(r'<[^>]+>', '', text)

    # Replace markdown or text bullets with emojis
    text = re.sub(r'^\s*[-*•]\s+', "✅ ", text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', "🔹 ", text, flags=re.MULTILINE)

    # Ensure double line breaks between sections
    text = re.sub(r'\n{2,}', '\n\n', text)  # collapse >2 line breaks
    text = re.sub(r'\n(?=\w)', r'\n\n', text)  # single newlines between paragraphs → double

    text = text.strip()

    if not text.startswith("🚀"):
        text = f"🚀 New Opportunity Alert!\n\n{text}"

    return text


def post_jd_on_linkedin(jd_id: str, company_id: str):
    '''This function will post given text on linkedin on behalf of user whose access token and urn is provided.'''

#   fetcing linkedin credentials from dynamodb
    response = auth_table.get_item(Key={"company_id": company_id})
    if 'Item' not in response:
        raise Exception("No LinkedIn auth data found for this company_id.")

    access_token = response['Item'].get("access_token")
    urn = response['Item'].get("organization_urn")

#  fetching job description from dynamodb
    jd_response = jd_table.get_item(Key={"jd_id": jd_id})
    if 'Item' not in jd_response:
        raise Exception("No Job Description found for this jd_id.")
    text = jd_response['Item'].get("job_description")
    
    text = format_for_linkedin_post(text)
    url = "https://api.linkedin.com/v2/ugcPosts"


    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }

    post_data = {
        "author" : urn,
        "lifecycleState" : "PUBLISHED",
        "specificContent" : {
            "com.linkedin.ugc.ShareContent" : {
                "shareCommentary" : {
                    "text" : text
                },
                "shareMediaCategory" : "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    response = requests.post(url, headers=headers, data=json.dumps(post_data))
    if response.status_code == 201:
        return "Post created successfully."
    else:
        return f"Failed to create post. Status code: {response.status_code}"
